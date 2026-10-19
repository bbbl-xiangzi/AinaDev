"use client";

export function VideoPlayer({ url, name }: { url: string; name: string }) {
  return (
    <video
      src={url}
      controls
      playsInline
      preload="metadata"
      aria-label={name}
      className="my-2 block max-h-[480px] w-full max-w-[720px] rounded-lg border border-[#d0d7de] bg-black"
    >
      <a href={url}>下载视频：{name}</a>
    </video>
  );
}
