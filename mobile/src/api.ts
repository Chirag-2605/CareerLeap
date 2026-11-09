import { auth } from "./firebase";

const API_URL = process.env.EXPO_PUBLIC_API_URL || "http://10.0.2.2:8000";

export async function analyzeResume(uri: string, name: string, mimeType: string, jobDescription: string) {
  if (!auth?.currentUser) throw new Error("Please sign in before scanning.");
  const token = await auth.currentUser.getIdToken();
  const form = new FormData();
  form.append("file", { uri, name, type: mimeType } as any);
  if (jobDescription.trim()) form.append("job_description", jobDescription.trim());

  const response = await fetch(`${API_URL}/api/v1/analyze`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || "Analysis failed. Please try again.");
  return payload;
}
