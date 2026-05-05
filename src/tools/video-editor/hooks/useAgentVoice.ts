import { useVoiceRecording } from "@/shared/hooks/useVoiceRecording.ts";

type UseAgentVoiceOptions = {
  onTranscription: (text: string) => void;
  onError?: (error: string) => void;
};

export function useAgentVoice({ onTranscription, onError }: UseAgentVoiceOptions) {
  const {
    startRecording,
    stopRecording,
    cancelRecording,
    toggleRecording,
    isRecording,
    isProcessing,
    audioLevel,
    remainingSeconds,
  } = useVoiceRecording({
    task: "transcribe_only",
    onError,
    onResult: ({ transcription }) => {
      onTranscription(transcription);
    },
  });

  return {
    startRecording,
    stopRecording,
    cancelRecording,
    toggleRecording,
    isRecording,
    isProcessing,
    audioLevel,
    remainingSeconds,
  };
}
