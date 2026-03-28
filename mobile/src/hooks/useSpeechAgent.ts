import { useState, useCallback } from "react";
import * as Speech from "expo-speech";
import { postSpeech } from "../services/api";

export type AgentState = "idle" | "thinking" | "speaking";

export function useSpeechAgent() {
  const [agentState, setAgentState] = useState<AgentState>("idle");
  const [lastResponse, setLastResponse] = useState<string>("");

  const askAgent = useCallback(async (text: string): Promise<void> => {
    setAgentState("thinking");

    try {
      const response = await postSpeech(text);
      setLastResponse(response);
      setAgentState("speaking");

      await new Promise<void>((resolve, reject) => {
        Speech.speak(response, {
          language: "en-US",
          pitch: 1.0,
          rate: 0.9,
          onDone: () => {
            setAgentState("idle");
            resolve();
          },
          onStopped: () => {
            setAgentState("idle");
            resolve();
          },
          onError: (error) => {
            setAgentState("idle");
            reject(error);
          },
        });
      });
    } catch (error) {
      setAgentState("idle");
      throw error;
    }
  }, []);

  const stopSpeaking = useCallback(() => {
    Speech.stop();
    setAgentState("idle");
  }, []);

  return { agentState, lastResponse, askAgent, stopSpeaking };
}
