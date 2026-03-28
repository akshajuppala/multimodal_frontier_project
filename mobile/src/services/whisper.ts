const OPENAI_API_KEY = process.env.EXPO_PUBLIC_OPENAI_API_KEY || "";

export async function transcribeAudio(audioUri: string): Promise<string> {
  const formData = new FormData();

  formData.append("file", {
    uri: audioUri,
    type: "audio/m4a",
    name: "recording.m4a",
  } as any);

  formData.append("model", "whisper-1");
  formData.append("language", "en");

  const response = await fetch(
    "https://api.openai.com/v1/audio/transcriptions",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${OPENAI_API_KEY}`,
      },
      body: formData,
    }
  );

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`Whisper API error (${response.status}): ${errorBody}`);
  }

  const data = await response.json();
  return data.text;
}
