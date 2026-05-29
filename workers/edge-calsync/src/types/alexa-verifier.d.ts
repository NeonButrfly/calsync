declare module "alexa-verifier" {
  export default function alexaVerifier(
    certUrl: string,
    signature: string,
    requestBody: string,
  ): Promise<void>;
}
