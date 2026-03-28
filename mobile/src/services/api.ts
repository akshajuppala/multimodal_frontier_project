const BACKEND_URL = process.env.EXPO_PUBLIC_BACKEND_URL || "http://localhost:8000";

export interface SpeechResponse {
  response: string;
}

export async function postSpeech(text: string): Promise<string> {
  const res = await fetch(`${BACKEND_URL}/speech`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });

  if (!res.ok) {
    throw new Error(`Speech API error: ${res.status}`);
  }

  const data: SpeechResponse = await res.json();
  return data.response;
}

export async function getHealth(): Promise<{ status: string; observations: number; items_tracked: number }> {
  const res = await fetch(`${BACKEND_URL}/health`);
  if (!res.ok) {
    throw new Error(`Health API error: ${res.status}`);
  }
  return res.json();
}
