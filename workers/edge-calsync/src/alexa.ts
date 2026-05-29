import { matchTokenToChannel } from "./auth";
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
    intent?: {
      name: string;
      slots?: Record<string, AlexaSlot>;
    };
  };
}

interface AlexaSlot {
  name?: string;
  value?: string;
}

interface AlexaListResponse {
  items?: Array<{
    title: string;
    date: string;
    start_time: string;
  }>;
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
  const payload = (await request.json()) as AlexaEnvelope;
  const skillId = extractSkillId(payload);
  const allowedSkillIds = allowedAlexaSkillIds(env);

  if (!skillId || (allowedSkillIds.length > 0 && !allowedSkillIds.includes(skillId))) {
    return new Response(
      JSON.stringify({
        ok: false,
        message: "Alexa skill ID is not allowed.",
        request_id: requestId,
      }),
      {
        status: 403,
        headers: {
          "content-type": "application/json; charset=utf-8",
        },
      },
    );
  }

  const accessToken = extractAccessToken(payload);
  if (!accessToken || (await matchTokenToChannel(accessToken, env)) !== "alexa") {
    return alexaResponse({
      speech:
        "Please link your CalSync account in the Alexa app before using this skill.",
      cardText:
        "Link your CalSync account in the Alexa app, then try again.",
      shouldEndSession: true,
      linkAccount: true,
    });
  }

  const requestType = payload.request.type;
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
    default:
      return alexaResponse({
        speech: "I do not support that request yet.",
        shouldEndSession: false,
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
      speech: `I added ${title} for ${humanDate(date)} at ${humanTime(startTime)}.`,
      shouldEndSession: true,
    });
  } catch {
    return alexaResponse({
      speech: "CalSync could not reach the calendar right now.",
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
