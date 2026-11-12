import { auth } from "./firebase";
import { Platform } from "react-native";

const API_URL = process.env.EXPO_PUBLIC_API_URL || "http://10.0.2.2:8000";

export async function analyzeResume(
  uri: string,
  name: string,
  mimeType: string,
  jobDescription: string,
  webFile?: Blob | null
) {
  const currentUser = auth?.currentUser;
  if (!currentUser) {
    throw new Error("Please sign in before analyzing a resume.");
  }

  const token = await currentUser.getIdToken();
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
  };

  const form = new FormData();

  if (Platform.OS === "web") {
    // Expo DocumentPicker exposes the browser File on web. Use it directly
    // instead of appending a React Native { uri, name, type } descriptor.
    let fileBlob = webFile;
    if (!fileBlob) {
      const fileResponse = await fetch(uri);
      if (!fileResponse.ok) {
        throw new Error("Unable to read the selected resume file.");
      }
      fileBlob = await fileResponse.blob();
    }
    form.append("file", fileBlob, name);
  } else {
    form.append(
      "file",
      {
        uri,
        name,
        type: mimeType || "application/octet-stream",
      } as any
    );
  }

  if (jobDescription.trim()) {
    form.append("job_description", jobDescription.trim());
  }

  const response = await fetch(`${API_URL}/api/v1/analyze`, {
    method: "POST",
    headers,
    body: form,
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail;
    const message = typeof detail === "string"
      ? detail
      : Array.isArray(detail)
        ? detail.map((item: any) => item.msg || item.message).filter(Boolean).join("; ")
        : "Analysis failed. Please try again.";
    throw new Error(message);
  }

  return payload;
}
