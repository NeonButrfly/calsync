import alexaVerifier from "alexa-verifier";
import { allowedAlexaSkillIds, type WorkerEnv } from "./env";
import { callOriginJson } from "./origin";

interface AlexaEnvelope {
  session?: {
    application?: {
      applicationId?: string;
    };
    user?: {
      accessToken?: string;
    };
  };
  context?: {
    System?: {
      application?: {
        applicationId?: string;
      };
      user?: {
        accessToken?: string;
      };
    };
  };
  request: {
    type: string;
    timestamp?: string;
    intent?: {
      name: string;
      slots?: Record<string, AlexaSlot>;
    };
  };
}

interface AlexaSimulationRequest {
  request_type?: string;
  intent_name?: string;
  slots?: Record<string, string>;
  timestamp?: string;
}

interface AlexaSlot {
  name?: string;
  value?: string;
}

interface AlexaListResponse {
  items?: Array<{
    appointment_id: string;
    title: string;
    date: string;
    start_time: string;
    end_time: string;
    timezone: string;
    status?: string;
  }>;
  message?: string;
  detail?: string;
}

interface AlexaAppointmentDetail {
  appointment_id: string;
  title: string;
  date: string;
  start_time: string;
  end_time: string;
  timezone: string;
  status: string;
}

interface AlexaAvailabilityResponse {
  items?: Array<{
    date: string;
    start_time: string;
    end_time: string;
    timezone: string;
  }>;
  message?: string;
  detail?: string;
}

interface AlexaSpeechOptions {
  speech: string;
  cardText?: string;
  reprompt?: string;
  shouldEndSession?: boolean;
  linkAccount?: boolean;
}

export async function handleAlexaRequest(
  request: Request,
  env: WorkerEnv,
  requestId: string,
): Promise<Response> {
  const requestBody = await request.text();
  const payload = JSON.parse(requestBody) as AlexaEnvelope;
  const skillId = extractSkillId(payload);
  const allowedSkillIds = allowedAlexaSkillIds(env);

  if (!skillId || (allowedSkillIds.length > 0 && !allowedSkillIds.includes(skillId))) {
    return alexaErrorResponse(403, "Alexa skill ID is not allowed.", requestId);
  }

  const certChainUrl = request.headers.get("SignatureCertChainUrl");
  const signature =
    request.headers.get("Signature-256") ?? request.headers.get("Signature");
  if (!certChainUrl || !signature) {
    return alexaErrorResponse(400, "Alexa signature headers are required.", requestId);
  }

  try {
    await alexaVerifier(certChainUrl, signature, requestBody);
  } catch (error) {
    const message =
      error instanceof Error && error.message ? error.message : String(error);
    return alexaErrorResponse(400, `Alexa request verification failed: ${message}`, requestId);
  }

  return dispatchAlexaPayload(payload, env, requestId, {
    skipAccountLinking: false,
  });
}

export async function simulateAlexaRequest(
  simulation: AlexaSimulationRequest,
  env: WorkerEnv,
  requestId: string,
): Promise<Response> {
  const requestType = simulation.request_type ?? "LaunchRequest";
  const timestamp = simulation.timestamp ?? new Date().toISOString();
  const slots = Object.fromEntries(
    Object.entries(simulation.slots ?? {}).filter(([, value]) => value?.trim()),
  );
  const payload: AlexaEnvelope = {
    request: {
      type: requestType,
      timestamp,
      intent:
        requestType === "IntentRequest" && simulation.intent_name
          ? {
              name: simulation.intent_name,
              slots: Object.fromEntries(
                Object.entries(slots).map(([name, value]) => [name, { value }]),
              ),
            }
          : undefined,
    },
  };
  return dispatchAlexaPayload(payload, env, requestId, {
    skipAccountLinking: true,
  });
}

async function dispatchAlexaPayload(
  payload: AlexaEnvelope,
  env: WorkerEnv,
  requestId: string,
  options: {
    skipAccountLinking: boolean;
  },
): Promise<Response> {
  const requestType = payload.request.type;
  if (!options.skipAccountLinking && requestType !== "SessionEndedRequest") {
    const accountLinkResponse = await ensureLinkedAccount(payload, env, requestId);
    if (accountLinkResponse) {
      return accountLinkResponse;
    }
  }
  if (requestType === "LaunchRequest") {
    return alexaResponse({
      speech:
        "Welcome to CalSync. You can ask what is on the calendar for a day, or create a new appointment.",
      reprompt:
        "Try saying, what appointments do I have on Monday, or create a dentist appointment on June first at ten A M.",
      shouldEndSession: false,
    });
  }

  if (requestType === "SessionEndedRequest") {
    return alexaResponse({
      speech: "Goodbye.",
      shouldEndSession: true,
    });
  }

  const intentName = payload.request.intent?.name;
  if (!intentName) {
    return alexaResponse({
      speech: "I did not understand that request.",
      reprompt:
        "You can ask what is on the calendar for a date, or create a new appointment.",
      shouldEndSession: false,
    });
  }

  switch (intentName) {
    case "AMAZON.HelpIntent":
      return alexaResponse({
        speech:
          "You can say, create an appointment called dentist on June first at ten A M ending at eleven A M. You can also say, what appointments do I have on Monday.",
        shouldEndSession: false,
      });
    case "AMAZON.CancelIntent":
    case "AMAZON.StopIntent":
      return alexaResponse({
        speech: "Okay, see you next time.",
        shouldEndSession: true,
      });
    case "AMAZON.FallbackIntent":
      return alexaResponse({
        speech:
          "I can help you create an appointment or read the calendar for a date.",
        shouldEndSession: false,
      });
    case "CreateAppointmentIntent":
      return handleCreateIntent(payload, env, requestId);
    case "ListAppointmentsIntent":
      return handleListIntent(payload, env, requestId);
    case "NextAppointmentIntent":
      return handleNextAppointmentIntent(payload, env, requestId);
    case "FindAvailabilityIntent":
      return handleFindAvailabilityIntent(payload, env, requestId);
    case "CancelAppointmentIntent":
      return handleCancelIntent(payload, env, requestId);
    case "RescheduleAppointmentIntent":
      return handleRescheduleIntent(payload, env, requestId);
    default:
      return alexaResponse({
        speech: "I do not support that request yet.",
        shouldEndSession: false,
      });
  }
}

async function ensureLinkedAccount(
  payload: AlexaEnvelope,
  env: WorkerEnv,
  requestId: string,
): Promise<Response | null> {
  try {
    const originResponse = await callOriginJson(env, {
      method: "POST",
      path: "/api/alexa/account-linking/validate",
      channel: "alexa",
      requestId,
      body: {
        access_token: extractAccessToken(payload),
      },
    });
    const originBody = (await originResponse.json()) as {
      data?: {
        account_linking_configured?: boolean;
        linked?: boolean;
      };
      message?: string;
      detail?: string;
    };
    if (!originResponse.ok) {
      return alexaResponse({
        speech:
          originBody.message ??
          originBody.detail ??
          "CalSync could not verify account linking right now.",
        shouldEndSession: true,
      });
    }

    if (originBody.data?.account_linking_configured && !originBody.data?.linked) {
      return alexaResponse({
        speech:
          "Please link your CalSync account in the Alexa app before using this skill.",
        shouldEndSession: true,
        linkAccount: true,
      });
    }
    return null;
  } catch {
    return alexaResponse({
      speech: "CalSync could not verify account linking right now.",
      shouldEndSession: true,
    });
  }
}

async function handleCreateIntent(
  payload: AlexaEnvelope,
  env: WorkerEnv,
  requestId: string,
): Promise<Response> {
  const title = slotValue(payload, "title");
  const date = slotValue(payload, "date");
  const startTime = slotValue(payload, "start_time");
  const endTime = slotValue(payload, "end_time") ?? addHour(startTime);
  const location = slotValue(payload, "location");
  const notes = slotValue(payload, "notes");
  const calendarName = slotValue(payload, "calendar_name");

  const missing = !title
    ? "title"
    : !date
      ? "date"
      : !startTime
        ? "start time"
        : !endTime
          ? "end time"
          : null;
  if (missing) {
    return alexaResponse({
      speech: `I still need the ${missing} for that appointment.`,
      reprompt: `Please tell me the ${missing}.`,
      shouldEndSession: false,
    });
  }

  try {
    const originResponse = await callOriginJson(env, {
      method: "POST",
      path: "/api/appointments",
      channel: "alexa",
      requestId,
      body: {
        title,
        date,
        start_time: startTime,
        end_time: endTime,
        timezone: env.ALEXA_DEFAULT_TIMEZONE || "America/Anchorage",
        all_day: false,
        location,
        notes,
        target_calendar_name: calendarName,
      },
    });
    const originBody = (await originResponse.json()) as {
      message?: string;
      detail?: string;
    };
    if (!originResponse.ok) {
      return alexaResponse({
        speech:
          originBody.message ??
          originBody.detail ??
          "I could not create that appointment.",
        shouldEndSession: true,
      });
    }

    return alexaResponse({
      speech: `I added ${title}${humanCalendarPhrase(calendarName)} for ${humanDate(date)} at ${humanTime(startTime)}.`,
      shouldEndSession: true,
    });
  } catch {
    return alexaResponse({
      speech: "CalSync could not reach the calendar right now.",
      shouldEndSession: true,
    });
  }
}

async function handleFindAvailabilityIntent(
  payload: AlexaEnvelope,
  env: WorkerEnv,
  requestId: string,
): Promise<Response> {
  const date = slotValue(payload, "date") ?? requestDate(payload, env);
  const endDate = slotValue(payload, "end_date") ?? date;
  const durationMinutes = slotValue(payload, "duration_minutes") ?? "60";

  try {
    const originResponse = await callOriginJson(env, {
      method: "GET",
      path:
        `/api/availability?date_from=${encodeURIComponent(date)}` +
        `&date_to=${encodeURIComponent(endDate)}` +
        `&duration_minutes=${encodeURIComponent(durationMinutes)}` +
        "&max_results=3",
      channel: "alexa",
      requestId,
    });
    const originBody = (await originResponse.json()) as AlexaAvailabilityResponse;
    if (!originResponse.ok) {
      return alexaResponse({
        speech:
          originBody.message ??
          originBody.detail ??
          "I could not look up availability right now.",
        shouldEndSession: true,
      });
    }

    const items = originBody.items ?? [];
    if (items.length === 0) {
      return alexaResponse({
        speech: `I could not find a ${durationMinutes} minute opening between ${humanDate(date)} and ${humanDate(endDate)}.`,
        shouldEndSession: true,
      });
    }

    return alexaResponse({
      speech: availabilitySpeech(items.slice(0, 3)),
      shouldEndSession: true,
    });
  } catch {
    return alexaResponse({
      speech: "CalSync could not look up availability right now.",
      shouldEndSession: true,
    });
  }
}

async function handleListIntent(
  payload: AlexaEnvelope,
  env: WorkerEnv,
  requestId: string,
): Promise<Response> {
  const date = slotValue(payload, "date");
  if (!date) {
    return alexaResponse({
      speech: "Tell me which date you want to check.",
      reprompt: "For example, say what appointments do I have on Monday.",
      shouldEndSession: false,
    });
  }

  try {
    const originResponse = await callOriginJson(env, {
      method: "GET",
      path: `/api/appointments?date_from=${encodeURIComponent(date)}&date_to=${encodeURIComponent(date)}`,
      channel: "alexa",
      requestId,
    });
    const originBody = (await originResponse.json()) as AlexaListResponse & {
      message?: string;
      detail?: string;
    };
    if (!originResponse.ok) {
      return alexaResponse({
        speech:
          originBody.message ??
          originBody.detail ??
          "I could not look up that date right now.",
        shouldEndSession: true,
      });
    }

    const items = originBody.items ?? [];
    if (items.length === 0) {
      return alexaResponse({
        speech: `You have no appointments on ${humanDate(date)}.`,
        shouldEndSession: true,
      });
    }

    const summary = items
      .slice(0, 3)
      .map((item) => `${item.title} at ${humanTime(item.start_time)}`)
      .join(", ");
    const overflow =
      items.length > 3 ? ` Plus ${items.length - 3} more appointments.` : "";
    return alexaResponse({
      speech: `On ${humanDate(date)}, you have ${summary}.${overflow}`,
      shouldEndSession: true,
    });
  } catch {
    return alexaResponse({
      speech: "CalSync could not read the calendar right now.",
      shouldEndSession: true,
    });
  }
}

async function handleNextAppointmentIntent(
  payload: AlexaEnvelope,
  env: WorkerEnv,
  requestId: string,
): Promise<Response> {
  const windowStart = requestDate(payload, env);
  const windowEnd = shiftDate(windowStart, 30);

  try {
    const originResponse = await callOriginJson(env, {
      method: "GET",
      path: `/api/appointments?date_from=${encodeURIComponent(windowStart)}&date_to=${encodeURIComponent(windowEnd)}`,
      channel: "alexa",
      requestId,
    });
    const originBody = (await originResponse.json()) as AlexaListResponse & {
      message?: string;
      detail?: string;
    };
    if (!originResponse.ok) {
      return alexaResponse({
        speech:
          originBody.message ??
          originBody.detail ??
          "I could not look up your next appointment right now.",
        shouldEndSession: true,
      });
    }

    const nextAppointment = (originBody.items ?? []).find(
      (item) => (item.status ?? "active") !== "cancelled",
    );
    if (!nextAppointment) {
      return alexaResponse({
        speech: "You do not have an upcoming appointment in the next 30 days.",
        shouldEndSession: true,
      });
    }

    return alexaResponse({
      speech: `Your next appointment is ${nextAppointment.title} on ${humanDate(nextAppointment.date)} at ${humanTime(nextAppointment.start_time)}.`,
      shouldEndSession: true,
    });
  } catch {
    return alexaResponse({
      speech: "CalSync could not read the calendar right now.",
      shouldEndSession: true,
    });
  }
}

async function handleCancelIntent(
  payload: AlexaEnvelope,
  env: WorkerEnv,
  requestId: string,
): Promise<Response> {
  const date = slotValue(payload, "date");
  const title = slotValue(payload, "title");
  const startTime = slotValue(payload, "start_time");

  if (!date || !title) {
    return alexaResponse({
      speech: "To cancel an appointment, tell me the title and date.",
      reprompt: "For example, say cancel dentist on Monday.",
      shouldEndSession: false,
    });
  }

  const match = await findMatchingAppointment(
    env,
    requestId,
    date,
    title,
    startTime,
  );
  if ("response" in match) {
    return match.response;
  }

  try {
    const originResponse = await callOriginJson(env, {
      method: "POST",
      path: `/api/appointments/${match.appointment.appointment_id}/cancel`,
      channel: "alexa",
      requestId,
    });
    const originBody = (await originResponse.json()) as {
      message?: string;
      detail?: string;
    };
    if (!originResponse.ok) {
      return alexaResponse({
        speech:
          originBody.message ??
          originBody.detail ??
          "I could not cancel that appointment right now.",
        shouldEndSession: true,
      });
    }

    return alexaResponse({
      speech: `I cancelled ${match.appointment.title} on ${humanDate(match.appointment.date)}.`,
      shouldEndSession: true,
    });
  } catch {
    return alexaResponse({
      speech: "CalSync could not cancel that appointment right now.",
      shouldEndSession: true,
    });
  }
}

async function handleRescheduleIntent(
  payload: AlexaEnvelope,
  env: WorkerEnv,
  requestId: string,
): Promise<Response> {
  const date = slotValue(payload, "date");
  const title = slotValue(payload, "title");
  const startTime = slotValue(payload, "start_time");
  const newDate = slotValue(payload, "new_date") ?? date;
  const newStartTime = slotValue(payload, "new_start_time");
  const newEndTime = slotValue(payload, "new_end_time");
  const newCalendarName = slotValue(payload, "new_calendar_name");

  if (!date || !title || !newStartTime) {
    return alexaResponse({
      speech:
        "To move an appointment, tell me the current title and date, plus the new time.",
      reprompt:
        "For example, say move dentist on Monday to Tuesday at 1 P M.",
      shouldEndSession: false,
    });
  }

  const match = await findMatchingAppointment(
    env,
    requestId,
    date,
    title,
    startTime,
  );
  if ("response" in match) {
    return match.response;
  }

  const detail = await fetchAppointmentDetail(
    env,
    requestId,
    match.appointment.appointment_id,
  );
  if ("response" in detail) {
    return detail.response;
  }

  const nextEndTime =
    newEndTime ?? shiftEndTime(detail.detail.start_time, detail.detail.end_time, newStartTime);
  if (!nextEndTime) {
    return alexaResponse({
      speech: "I could not work out the new end time for that appointment.",
      shouldEndSession: true,
    });
  }

  try {
    const originResponse = await callOriginJson(env, {
      method: "PATCH",
      path: `/api/appointments/${match.appointment.appointment_id}`,
      channel: "alexa",
      requestId,
      body: {
        date: newDate,
        start_time: newStartTime,
        end_time: nextEndTime,
        timezone: detail.detail.timezone,
        target_calendar_name: newCalendarName,
      },
    });
    const originBody = (await originResponse.json()) as {
      message?: string;
      detail?: string;
    };
    if (!originResponse.ok) {
      return alexaResponse({
        speech:
          originBody.message ??
          originBody.detail ??
          "I could not move that appointment right now.",
        shouldEndSession: true,
      });
    }

    return alexaResponse({
      speech: `I moved ${match.appointment.title}${humanCalendarPhrase(newCalendarName)} on ${humanDate(newDate)} at ${humanTime(newStartTime)}.`,
      shouldEndSession: true,
    });
  } catch {
    return alexaResponse({
      speech: "CalSync could not move that appointment right now.",
      shouldEndSession: true,
    });
  }
}

async function findMatchingAppointment(
  env: WorkerEnv,
  requestId: string,
  date: string,
  title: string,
  startTime: string | null,
): Promise<
  | { appointment: AlexaListResponse["items"][number] }
  | { response: Response }
> {
  try {
    const originResponse = await callOriginJson(env, {
      method: "GET",
      path: `/api/appointments?date_from=${encodeURIComponent(date)}&date_to=${encodeURIComponent(date)}`,
      channel: "alexa",
      requestId,
    });
    const originBody = (await originResponse.json()) as AlexaListResponse;
    if (!originResponse.ok) {
      return {
        response: alexaResponse({
          speech:
            originBody.message ??
            originBody.detail ??
            "I could not look up that date right now.",
          shouldEndSession: true,
        }),
      };
    }

    const normalizedTitle = normalizeTitle(title);
    const activeItems = (originBody.items ?? []).filter(
      (item) => (item.status ?? "active") !== "cancelled",
    );
    const exactMatches = activeItems.filter(
      (item) => normalizeTitle(item.title) === normalizedTitle,
    );
    const fuzzyMatches =
      exactMatches.length > 0
        ? exactMatches
        : activeItems.filter((item) =>
            normalizeTitle(item.title).includes(normalizedTitle),
          );
    const timeFiltered =
      startTime != null
        ? fuzzyMatches.filter((item) => item.start_time === startTime)
        : fuzzyMatches;

    if (timeFiltered.length === 0) {
      return {
        response: alexaResponse({
          speech: `I could not find ${title} on ${humanDate(date)}.`,
          shouldEndSession: true,
        }),
      };
    }

    if (timeFiltered.length > 1) {
      return {
        response: alexaResponse({
          speech: `I found more than one ${title} on ${humanDate(date)}. Please include the start time so I know which one you mean.`,
          shouldEndSession: false,
        }),
      };
    }

    return { appointment: timeFiltered[0] };
  } catch {
    return {
      response: alexaResponse({
        speech: "CalSync could not read the calendar right now.",
        shouldEndSession: true,
      }),
    };
  }
}

async function fetchAppointmentDetail(
  env: WorkerEnv,
  requestId: string,
  appointmentId: string,
): Promise<{ detail: AlexaAppointmentDetail } | { response: Response }> {
  try {
    const originResponse = await callOriginJson(env, {
      method: "GET",
      path: `/api/appointments/${appointmentId}`,
      channel: "alexa",
      requestId,
    });
    const originBody = (await originResponse.json()) as AlexaAppointmentDetail & {
      message?: string;
      detail?: string;
    };
    if (!originResponse.ok) {
      return {
        response: alexaResponse({
          speech:
            originBody.message ??
            originBody.detail ??
            "I could not read that appointment right now.",
          shouldEndSession: true,
        }),
      };
    }
    return { detail: originBody };
  } catch {
    return {
      response: alexaResponse({
        speech: "CalSync could not read that appointment right now.",
        shouldEndSession: true,
      }),
    };
  }
}

function extractSkillId(payload: AlexaEnvelope): string | null {
  return (
    payload.context?.System?.application?.applicationId ??
    payload.session?.application?.applicationId ??
    null
  );
}

function extractAccessToken(payload: AlexaEnvelope): string | null {
  return (
    payload.context?.System?.user?.accessToken ??
    payload.session?.user?.accessToken ??
    null
  );
}

function slotValue(payload: AlexaEnvelope, slotName: string): string | null {
  const value = payload.request.intent?.slots?.[slotName]?.value?.trim();
  return value || null;
}

function normalizeTitle(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function addHour(time: string | null): string | null {
  if (!time || !/^\d{2}:\d{2}$/.test(time)) {
    return null;
  }
  const [hoursText, minutesText] = time.split(":");
  const hours = Number(hoursText);
  const minutes = Number(minutesText);
  const totalMinutes = hours * 60 + minutes + 60;
  const normalizedHours = Math.floor((totalMinutes % (24 * 60)) / 60);
  const normalizedMinutes = totalMinutes % 60;
  return `${String(normalizedHours).padStart(2, "0")}:${String(normalizedMinutes).padStart(2, "0")}`;
}

function shiftEndTime(
  originalStart: string,
  originalEnd: string,
  newStart: string,
): string | null {
  if (
    !/^\d{2}:\d{2}$/.test(originalStart) ||
    !/^\d{2}:\d{2}$/.test(originalEnd) ||
    !/^\d{2}:\d{2}$/.test(newStart)
  ) {
    return null;
  }
  const duration = timeToMinutes(originalEnd) - timeToMinutes(originalStart);
  if (duration <= 0) {
    return null;
  }
  const newEndMinutes = timeToMinutes(newStart) + duration;
  return minutesToTime(newEndMinutes);
}

function timeToMinutes(time: string): number {
  const [hoursText, minutesText] = time.split(":");
  return Number(hoursText) * 60 + Number(minutesText);
}

function minutesToTime(totalMinutes: number): string {
  const normalized = ((totalMinutes % (24 * 60)) + 24 * 60) % (24 * 60);
  const hours = Math.floor(normalized / 60);
  const minutes = normalized % 60;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

function humanDate(date: string): string {
  const displayDate = new Date(`${date}T12:00:00Z`);
  return displayDate.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

function humanTime(time: string): string {
  const [hoursText, minutesText] = time.split(":");
  const displayDate = new Date(
    Date.UTC(2026, 0, 1, Number(hoursText), Number(minutesText)),
  );
  return displayDate.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    timeZone: "UTC",
  });
}

function humanCalendarPhrase(calendarName: string | null): string {
  if (!calendarName) {
    return "";
  }
  return ` to the ${calendarName} calendar`;
}

function availabilitySpeech(
  items: Array<{
    date: string;
    start_time: string;
    end_time: string;
    timezone: string;
  }>,
): string {
  const grouped = new Map<string, string[]>();
  for (const item of items) {
    const times = grouped.get(item.date) ?? [];
    times.push(humanTime(item.start_time));
    grouped.set(item.date, times);
  }
  const parts = Array.from(grouped.entries()).map(([day, times]) => {
    if (times.length === 1) {
      return `${humanDate(day)} at ${times[0]}`;
    }
    return `${humanDate(day)} at ${times.join(" and ")}`;
  });
  return `I found openings on ${parts.join(" and ")}.`;
}

function requestDate(payload: AlexaEnvelope, env: WorkerEnv): string {
  const timezone = env.ALEXA_DEFAULT_TIMEZONE || "America/Anchorage";
  const requestTimestamp = payload.request.timestamp
    ? new Date(payload.request.timestamp)
    : new Date();
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(requestTimestamp);
}

function shiftDate(dateValue: string, days: number): string {
  const parsed = new Date(`${dateValue}T12:00:00Z`);
  parsed.setUTCDate(parsed.getUTCDate() + days);
  return parsed.toISOString().slice(0, 10);
}

function alexaResponse(options: AlexaSpeechOptions): Response {
  const {
    speech,
    cardText,
    reprompt,
    shouldEndSession = true,
    linkAccount = false,
  } = options;
  const card = linkAccount
    ? { type: "LinkAccount" as const }
    : {
        type: "Simple" as const,
        title: "CalSync",
        content: cardText ?? speech,
      };

  return new Response(
    JSON.stringify({
      version: "1.0",
      response: {
        outputSpeech: {
          type: "PlainText",
          text: speech,
        },
        card,
        reprompt: reprompt
          ? {
              outputSpeech: {
                type: "PlainText",
                text: reprompt,
              },
            }
          : undefined,
        shouldEndSession,
      },
    }),
    {
      status: 200,
      headers: {
        "content-type": "application/json; charset=utf-8",
      },
    },
  );
}

function alexaErrorResponse(
  status: number,
  message: string,
  requestId: string,
): Response {
  return new Response(
    JSON.stringify({
      ok: false,
      message,
      request_id: requestId,
    }),
    {
      status,
      headers: {
        "content-type": "application/json; charset=utf-8",
      },
    },
  );
}
