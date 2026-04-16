import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

function extractShortcode(url: string): string | null {
  const match = url.match(new RegExp("/(reel|p|reels|tv)/([A-Za-z0-9_-]+)"));
  if (match) return match[2];
  const storyMatch = url.match(new RegExp("/stories/[^/]+/(\\d+)"));
  if (storyMatch) return storyMatch[1];
  return null;
}

function decodeIgUrl(s: string): string {
  return s.split("\\u0026").join("&").split("&amp;").join("&");
}

async function tryDownloadMethods(
  url: string
): Promise<{ videoUrl?: string; imageUrl?: string; error?: string }> {
  const shortcode = extractShortcode(url);

  // Method 1: Instagram API with app ID
  if (shortcode) {
    try {
      const apiUrl = `https://www.instagram.com/p/${shortcode}/?__a=1&__d=dis`;
      const resp = await fetch(apiUrl, {
        headers: {
          "User-Agent":
            "Instagram 275.0.0.27.98 Android (33/13; 420dpi; 1080x2400; samsung; SM-G991B)",
          Accept: "*/*",
          "X-IG-App-ID": "936619743392459",
        },
      });
      if (resp.ok) {
        const data = await resp.json();
        const item = data?.items?.[0] || data?.graphql?.shortcode_media;
        if (item?.video_versions?.[0]?.url)
          return { videoUrl: item.video_versions[0].url };
        if (item?.video_url) return { videoUrl: item.video_url };
        if (item?.image_versions2?.candidates?.[0]?.url)
          return { imageUrl: item.image_versions2.candidates[0].url };
        if (item?.display_url) return { imageUrl: item.display_url };
      }
    } catch (_) {
      /* next */
    }
  }

  // Method 2: Fetch HTML and extract from meta/embedded JSON
  try {
    const pageUrl = shortcode
      ? `https://www.instagram.com/p/${shortcode}/`
      : url;
    const resp = await fetch(pageUrl, {
      headers: {
        "User-Agent":
          "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
        Accept: "text/html,*/*",
      },
      redirect: "follow",
    });
    const html = await resp.text();

    // Video patterns
    const vidPatterns = [
      new RegExp('"video_url"\\s*:\\s*"([^"]+)"'),
      new RegExp('property="og:video"\\s+content="([^"]+)"'),
      new RegExp('content="([^"]+)"\\s+property="og:video"'),
      new RegExp('"contentUrl"\\s*:\\s*"([^"]+)"'),
    ];
    for (const p of vidPatterns) {
      const m = html.match(p);
      if (m) return { videoUrl: decodeIgUrl(m[1]) };
    }

    // Image patterns
    const imgPatterns = [
      new RegExp('property="og:image"\\s+content="([^"]+)"'),
      new RegExp('content="([^"]+)"\\s+property="og:image"'),
      new RegExp('"display_url"\\s*:\\s*"([^"]+)"'),
    ];
    for (const p of imgPatterns) {
      const m = html.match(p);
      if (m) return { imageUrl: decodeIgUrl(m[1]) };
    }
  } catch (_) {
    /* next */
  }

  // Method 3: Embed endpoint
  if (shortcode) {
    try {
      const resp = await fetch(
        `https://www.instagram.com/p/${shortcode}/embed/`,
        {
          headers: {
            "User-Agent":
              "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
          },
        }
      );
      const html = await resp.text();
      const vidMatch = html.match(new RegExp('"video_url"\\s*:\\s*"([^"]+)"'));
      if (vidMatch) return { videoUrl: decodeIgUrl(vidMatch[1]) };
      const imgMatch = html.match(
        new RegExp('class="EmbeddedMediaImage"[^>]*src="([^"]+)"')
      );
      if (imgMatch) return { imageUrl: decodeIgUrl(imgMatch[1]) };
    } catch (_) {
      /* next */
    }
  }

  return {
    error:
      'Could not extract media from this URL. Try saving the video to your phone first (long-press the reel > Save), then use the Video Frames tab to upload it directly.',
  };
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS")
    return new Response(null, { headers: corsHeaders });
  if (req.method !== "POST")
    return new Response("Method not allowed", {
      status: 405,
      headers: corsHeaders,
    });

  try {
    const { url } = await req.json();
    if (
      !url ||
      (!url.includes("instagram.com") && !url.includes("instagr.am"))
    ) {
      return new Response(JSON.stringify({ error: "Invalid Instagram URL" }), {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const result = await tryDownloadMethods(url);
    if (result.error) {
      return new Response(JSON.stringify({ error: result.error }), {
        status: 422,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const mediaUrl = result.videoUrl || result.imageUrl;
    if (!mediaUrl) {
      return new Response(JSON.stringify({ error: "No media found" }), {
        status: 404,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // Proxy the media
    const mediaResp = await fetch(mediaUrl, {
      headers: { "User-Agent": "Mozilla/5.0" },
    });
    if (!mediaResp.ok) {
      return new Response(
        JSON.stringify({ error: "Failed to download media" }),
        {
          status: 502,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        }
      );
    }

    const blob = await mediaResp.blob();
    return new Response(blob, {
      headers: {
        ...corsHeaders,
        "Content-Type": result.videoUrl ? "video/mp4" : "image/jpeg",
        "X-Media-Type": result.videoUrl ? "video" : "image",
      },
    });
  } catch (e) {
    return new Response(JSON.stringify({ error: String(e) }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
