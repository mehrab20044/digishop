import { useEffect, useRef, useState } from "react";
import "./banners.css";


export function BannerCard({ banner, eager = false }) {
  const videoRef = useRef(null);
  const [paused, setPaused] = useState(true);

  const [mobile, setMobile] = useState(
    () => Boolean(window.matchMedia?.("(max-width: 650px)").matches),
  );

  const isVideo = banner.media_type === "video";

  const image = mobile
    ? banner.mobile_image_url || banner.image_url
    : banner.image_url || banner.mobile_image_url;

  const video = mobile
    ? banner.mobile_video_url || banner.video_url
    : banner.video_url || banner.mobile_video_url;

  const label = banner.alt || banner.title || "بنر فروشگاه";

  useEffect(() => {
    const query = window.matchMedia?.("(max-width: 650px)");
    if (!query) return undefined;

    const update = () => setMobile(query.matches);

    query.addEventListener?.("change", update);

    return () => query.removeEventListener?.("change", update);
  }, []);

  useEffect(() => {
    const element = videoRef.current;
    if (!element) return undefined;

    const reducedMotion = window.matchMedia?.(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    if (
      banner.autoplay &&
      !reducedMotion &&
      !navigator.connection?.saveData
    ) {
      element.play().catch(() => {
        // مرورگر ممکن است پخش خودکار را نپذیرد.
      });
    }

    function visibilityChanged() {
      if (document.hidden) element.pause();
    }

    document.addEventListener("visibilitychange", visibilityChanged);

    return () => {
      document.removeEventListener(
        "visibilitychange",
        visibilityChanged,
      );
      element.pause();
    };
  }, [video, banner.autoplay]);

  if ((!isVideo && !image) || (isVideo && !video)) return null;

  const media = isVideo ? (
    <video
      ref={videoRef}
      key={video}
      src={video}
      poster={image || undefined}
      muted
      loop
      playsInline
      preload="metadata"
      aria-label={label}
      onPlay={() => setPaused(false)}
      onPause={() => setPaused(true)}
    />
  ) : (
    <img
      src={image}
      alt={label}
      loading={eager ? "eager" : "lazy"}
      fetchPriority={eager ? "high" : "auto"}
      decoding="async"
    />
  );

  async function togglePlayback() {
    const element = videoRef.current;
    if (!element) return;

    if (element.paused) {
      try {
        await element.play();
      } catch {
        setPaused(true);
      }
    } else {
      element.pause();
    }
  }

  return (
    <div className="ad-banner">
      {banner.href ? (
        <a
          className="ad-banner-link"
          href={banner.href}
          aria-label={label}
        >
          {media}
        </a>
      ) : (
        <div className="ad-banner-link">{media}</div>
      )}

      {isVideo && (
        <button
          type="button"
          className="ad-video-control"
          aria-label={paused ? "پخش ویدیو" : "توقف ویدیو"}
          onClick={togglePlayback}
        >
          {paused ? "▶" : "Ⅱ"}
        </button>
      )}
    </div>
  );
}

const EMPTY_BANNERS = {
  hero: [],
  tiles: [],
  top: [],
  bottom: [],
};

function useBannerFeed() {
  const [data, setData] = useState(EMPTY_BANNERS);

  useEffect(() => {
    const controller = new AbortController();
    let timer;

    async function load() {
      let delay = 15000;

      try {
        const response = await fetch("/api/v1/content/banners/", {
          cache: "no-store",
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error("دریافت بنرها انجام نشد.");
        }

        const result = await response.json();

        if (controller.signal.aborted) return;

        setData(result);
        delay = 60000;

        if (result.next_change_at && result.server_time) {
          const remaining =
            Date.parse(result.next_change_at) -
            Date.parse(result.server_time);

          if (Number.isFinite(remaining)) {
            delay = Math.max(1000, Math.min(60000, remaining + 100));
          }
        }
      } catch {
        if (!controller.signal.aborted) {
          // بنر زمان‌دارِ قدیمی پس از قطع ارتباط باقی نماند.
          setData(EMPTY_BANNERS);
        }
      } finally {
        if (!controller.signal.aborted) {
          timer = window.setTimeout(load, delay);
        }
      }
    }

    load();

    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, []);

  return data;
}

function BannerSlider({ rows }) {
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const [interacting, setInteracting] = useState(false);
  const [playing, setPlaying] = useState(false);

  const current = Math.min(index, Math.max(0, rows.length - 1));
  const interval = rows[current]?.interval || 6;

  useEffect(() => {
    if (
      rows.length < 2 ||
      paused ||
      interacting ||
      playing ||
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
    ) {
      return undefined;
    }

    const timer = window.setInterval(() => {
      if (!document.hidden) {
        setIndex((value) => (value + 1) % rows.length);
      }
    }, interval * 1000);

    return () => window.clearInterval(timer);
  }, [rows.length, current, interval, paused, interacting, playing]);

  if (!rows.length) return null;

  function goTo(next) {
    setPlaying(false);
    setIndex((next + rows.length) % rows.length);
  }

  return (
    <section
      className="bn-carousel"
      aria-label="پیشنهادهای فروشگاه"
      onMouseEnter={() => setInteracting(true)}
      onMouseLeave={() => {
        setInteracting(
          document.activeElement instanceof Element &&
          document.activeElement.closest(".bn-carousel") !== null,
        );
      }}
      onFocusCapture={() => setInteracting(true)}
      onBlurCapture={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) {
          setInteracting(event.currentTarget.matches(":hover"));
        }
      }}
      onPlayCapture={() => setPlaying(true)}
      onPauseCapture={() => setPlaying(false)}
      onEndedCapture={() => setPlaying(false)}
    >
      <BannerCard
        key={rows[current].id}
        banner={rows[current]}
        eager
      />

      {rows.length > 1 && (
        <div className="bn-controls">
          <button
            type="button"
            aria-label="بنر قبلی"
            onClick={() => goTo(current - 1)}
          >
            ›
          </button>

          <div className="bn-dots">
            {rows.map((row, position) => (
              <button
                key={row.id}
                type="button"
                aria-label={`نمایش بنر ${position + 1}`}
                aria-pressed={position === current}
                className={position === current ? "is-active" : ""}
                onClick={() => goTo(position)}
              />
            ))}
          </div>

          <button
            type="button"
            aria-label="بنر بعدی"
            onClick={() => goTo(current + 1)}
          >
            ‹
          </button>

          <button
            type="button"
            className="bn-pause"
            aria-label={paused ? "شروع نمایش خودکار" : "توقف نمایش خودکار"}
            onClick={() => setPaused((value) => !value)}
          >
            {paused ? "▶" : "Ⅱ"}
          </button>
        </div>
      )}
    </section>
  );
}

export function Promotions({ placement }) {
  const data = useBannerFeed();
  const rows = data[placement] || [];

  if (!rows.length) return null;

  if (placement === "hero") {
    return <BannerSlider rows={rows} />;
  }

  return (
<section
  className={
    placement === "tiles"
      ? "bn-tiles"
      : `ads-placement ads-placement--${placement}`
  }
  aria-label="تبلیغ‌های فروشگاه"
>
      {rows.map((row) => (
        <BannerCard key={row.id} banner={row} />
      ))}
    </section>
  );
}

export function TopPromotions() {
  return (
    <div className="bn-top">
      <Promotions placement="top" />
    </div>
  );
}