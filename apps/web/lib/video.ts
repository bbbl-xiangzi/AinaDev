/** Only render videos from the application's generated upload paths. */
export function isUploadedVideo(url?: string): boolean {
  return !!url && /^\/uploads\/\d{6}\/\d{2}\/[a-f0-9]{32}\.(mp4|webm)$/i.test(url);
}
