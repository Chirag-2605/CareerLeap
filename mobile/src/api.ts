import { auth } from "./firebase";
import { Platform } from "react-native";
import { File as ExpoFile } from "expo-file-system";

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

  let token: string;
  try {
    token = await currentUser.getIdToken(true);
  } catch {
    throw new Error("Your session couldn't be refreshed. Please sign in again.");
  }
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
    // Expo SDK 58's FormData serializer accepts Blob implementations.
    // ExpoFile implements Blob; the legacy { uri, name, type } object is rejected.
    const nativeFile = new ExpoFile(uri);
    form.append("file", nativeFile, name);
  }

  if (jobDescription.trim()) {
    form.append("job_description", jobDescription.trim());
  }

  let response: Response;
  try {
    response = await fetch(`${API_URL}/api/v1/analyze`, {
      method: "POST",
      headers,
      body: form,
    });
  } catch {
    throw new Error("Couldn't connect to CareerLeap. Check your internet connection and try again.");
  }

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
