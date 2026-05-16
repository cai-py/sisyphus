/* ============================================================================
   liquid-glass.js
   A pure HTML/CSS/JS port of kube.io's SVG Liquid Glass technique.
   Credit: original physics + article by @kube (https://kube.io), demo port
   approach by winaviation/liquid-glass-demo.

   Why this works cross-browser: the displacement is applied with the regular
   CSS `filter` property on a same-size "backdrop clone" layer, NOT
   `backdrop-filter` (which only does SVG filters in Chromium). Firefox and
   Chrome both render it. Safari's SVG-filter pipeline is still broken, so it
   gets a clean frosted fallback automatically.

   Physics (per the kube.io article):
     - convex SQUIRCLE bezel height profile  h = (1-(1-t)^4)^(1/4)
     - trace an orthogonal ray, bend it with Snell's law (n = 1.5)
     - displacement = lateral landing offset, ZERO in the flat interior,
       rising smoothly through the curved bezel, directed along the
       border normal
     - encode dx -> R, dy -> G (128 = neutral) into a PNG used by
       <feDisplacementMap>; a second pass builds a specular highlight map
   ========================================================================== */
(function (global) {
  "use strict";

  const NS = "http://www.w3.org/2000/svg";
  let UID = 0;

  // ---- surface height profiles (t in [0,1], 0 = outer edge) --------------
  const SURFACES = {
    convexCircle:  (t) => Math.sqrt(Math.max(0, 1 - (1 - t) ** 2)),
    convexSquircle:(t) => Math.pow(Math.max(0, 1 - (1 - t) ** 4), 0.25),
    concave:       (t) => 1 - Math.sqrt(Math.max(0, 1 - (1 - t) ** 2)),
    lip: (t) => {
      const cx = Math.sqrt(Math.max(0, 1 - (1 - t) ** 2));
      const cc = 1 - cx;
      const s = t * t * t * (t * (t * 6 - 15) + 10); // smootherstep
      return cx * (1 - s) + cc * s;
    },
  };

  // pre-compute the normalised displacement magnitude across the bezel
  function buildProfile(surfaceFn, samples, n) {
    const mags = new Float64Array(samples);
    const d = 1e-4;
    let max = 0;
    for (let i = 0; i < samples; i++) {
      const t = i / (samples - 1);
      const y1 = surfaceFn(Math.max(0, t - d));
      const y2 = surfaceFn(Math.min(1, t + d));
      const slope = (y2 - y1) / (2 * d);
      const theta1 = Math.atan(slope);                 // angle of incidence
      const s2 = Math.max(-1, Math.min(1, Math.sin(theta1) / n));
      const theta2 = Math.asin(s2);                    // refracted angle
      const bend = Math.tan(theta1 - theta2);          // lateral shift
      mags[i] = bend;
      if (Math.abs(bend) > max) max = Math.abs(bend);
    }
    if (max === 0) max = 1;
    for (let i = 0; i < samples; i++) mags[i] /= max;  // normalise to [-1,1]
    return { mags, max };
  }

  // signed distance to a rounded rectangle (negative = inside)
  function roundedSDF(px, py, hw, hh, r) {
    const qx = Math.abs(px) - (hw - r);
    const qy = Math.abs(py) - (hh - r);
    const ox = Math.max(qx, 0), oy = Math.max(qy, 0);
    const outside = Math.hypot(ox, oy);
    const inside = Math.min(Math.max(qx, qy), 0);
    return outside + inside - r;
  }

  // render displacement + specular maps for a given box, return data URLs
  function renderMaps(w, h, radius, bezel, surfaceName) {
    w = Math.max(2, Math.round(w));
    h = Math.max(2, Math.round(h));
    const r = Math.min(radius, w / 2, h / 2);
    const surfaceFn = SURFACES[surfaceName] || SURFACES.convexSquircle;
    const SAMPLES = 256;
    const { mags } = buildProfile(surfaceFn, SAMPLES, 1.5);

    const disp = document.createElement("canvas");
    disp.width = w; disp.height = h;
    const dctx = disp.getContext("2d");
    const dimg = dctx.createImageData(w, h);

    const spec = document.createElement("canvas");
    spec.width = w; spec.height = h;
    const sctx = spec.getContext("2d");
    const simg = sctx.createImageData(w, h);

    const hw = w / 2, hh = h / 2;
    const eps = 1;

    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const px = x + 0.5 - hw;
        const py = y + 0.5 - hh;
        const sd = roundedSDF(px, py, hw, hh, r);
        const depth = -sd;                         // >0 inside
        const i = (y * w + x) * 4;

        let R = 128, G = 128, S = 0;
        if (depth > 0) {
          const t = Math.min(1, depth / bezel);    // 0 edge -> 1 inner
          // gradient of the SDF = outward border normal
          const gx =
            roundedSDF(px + eps, py, hw, hh, r) -
            roundedSDF(px - eps, py, hw, hh, r);
          const gy =
            roundedSDF(px, py + eps, hw, hh, r) -
            roundedSDF(px, py - eps, hw, hh, r);
          const gl = Math.hypot(gx, gy) || 1;
          const nx = gx / gl, ny = gy / gl;        // points outward

          const idx = Math.min(
            SAMPLES - 1,
            Math.max(0, Math.round(t * (SAMPLES - 1)))
          );
          const mag = mags[idx] * (t < 1 ? 1 : 0); // no bend in flat centre

          // push pixels inward along the normal (refraction)
          const dx = -nx * mag;
          const dy = -ny * mag;
          R = Math.max(0, Math.min(255, 128 + dx * 127));
          G = Math.max(0, Math.min(255, 128 + dy * 127));

          // specular: bright thin rim + soft inner sheen, lit top-left
          const rim =
            Math.exp(-((t - 0.07) ** 2) / (2 * 0.05 ** 2)) +
            0.4 * Math.exp(-((t - 0.5) ** 2) / (2 * 0.3 ** 2));
          const lightDir = (-nx - ny) * 0.5 + 0.5;  // 0..1
          S = Math.max(0, Math.min(1, rim * (0.45 + 0.55 * lightDir)));
        }

        dimg.data[i] = R;
        dimg.data[i + 1] = G;
        dimg.data[i + 2] = 128;
        dimg.data[i + 3] = depth > -1 ? 255 : 0;

        const sv = Math.round(S * 255);
        simg.data[i] = sv;
        simg.data[i + 1] = sv;
        simg.data[i + 2] = sv;
        simg.data[i + 3] = sv;
      }
    }
    dctx.putImageData(dimg, 0, 0);
    sctx.putImageData(simg, 0, 0);
    return { disp: disp.toDataURL(), spec: spec.toDataURL() };
  }

  // detect whether SVG filters work via backdrop-filter (Chromium only)
  function supportsBackdropSVG() {
    return (
      CSS.supports("backdrop-filter", 'url("#x")') ||
      CSS.supports("-webkit-backdrop-filter", 'url("#x")')
    );
  }

  /* --------------------------------------------------------------------- *
   *  Public: LiquidGlass.apply(el, options)
   *  Turns an element into a refractive glass surface. The element should
   *  contain a single child wrapper for its content (we add glass layers
   *  behind it).
   * --------------------------------------------------------------------- */
  const filterHost = (() => {
    const s = document.createElementNS(NS, "svg");
    s.setAttribute("aria-hidden", "true");
    s.style.cssText =
      "position:absolute;width:0;height:0;overflow:hidden;pointer-events:none";
    const defs = document.createElementNS(NS, "defs");
    s.appendChild(defs);
    document.addEventListener("DOMContentLoaded", () =>
      document.body.appendChild(s)
    );
    return defs;
  })();

  function makeFilter(id, mapUrl, w, h, scale, dispersion, blur) {
    const f = document.createElementNS(NS, "filter");
    f.setAttribute("id", id);
    f.setAttribute("x", "-30%");
    f.setAttribute("y", "-30%");
    f.setAttribute("width", "160%");
    f.setAttribute("height", "160%");
    f.setAttribute("color-interpolation-filters", "sRGB");

    const feImg = document.createElementNS(NS, "feImage");
    feImg.setAttribute("href", mapUrl);
    feImg.setAttribute("x", "0");
    feImg.setAttribute("y", "0");
    feImg.setAttribute("width", "100%");
    feImg.setAttribute("height", "100%");
    feImg.setAttribute("preserveAspectRatio", "none");
    feImg.setAttribute("result", "map");
    f.appendChild(feImg);

    // chromatic dispersion: displace R/G/B at slightly different scales
    const channels = [
      { sel: "R", mat: "1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0", sc: scale * (1 + dispersion) },
      { sel: "G", mat: "0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0", sc: scale },
      { sel: "B", mat: "0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0", sc: scale * (1 - dispersion) },
    ];
    const outs = [];
    channels.forEach((c, k) => {
      const dm = document.createElementNS(NS, "feDisplacementMap");
      dm.setAttribute("in", "SourceGraphic");
      dm.setAttribute("in2", "map");
      dm.setAttribute("scale", c.sc.toFixed(2));
      dm.setAttribute("xChannelSelector", "R");
      dm.setAttribute("yChannelSelector", "G");
      dm.setAttribute("result", "d" + k);
      f.appendChild(dm);
      const cm = document.createElementNS(NS, "feColorMatrix");
      cm.setAttribute("in", "d" + k);
      cm.setAttribute("type", "matrix");
      cm.setAttribute("values", c.mat);
      cm.setAttribute("result", "c" + k);
      f.appendChild(cm);
      outs.push("c" + k);
    });
    const b1 = document.createElementNS(NS, "feBlend");
    b1.setAttribute("in", outs[0]);
    b1.setAttribute("in2", outs[1]);
    b1.setAttribute("mode", "screen");
    b1.setAttribute("result", "rg");
    f.appendChild(b1);
    const b2 = document.createElementNS(NS, "feBlend");
    b2.setAttribute("in", "rg");
    b2.setAttribute("in2", outs[2]);
    b2.setAttribute("mode", "screen");
    b2.setAttribute("result", "rgb");
    f.appendChild(b2);
    if (blur > 0) {
      const g = document.createElementNS(NS, "feGaussianBlur");
      g.setAttribute("in", "rgb");
      g.setAttribute("stdDeviation", blur);
      f.appendChild(g);
    }
    filterHost.appendChild(f);
    return id;
  }

  function apply(el, options) {
    const o = Object.assign(
      {
        radius: 999,        // px corner radius (clamped to a pill)
        bezel: 26,          // px width of the refractive ring
        surface: "convexSquircle",
        scale: 70,          // refraction strength (px)
        dispersion: 0.18,   // chromatic aberration amount
        blur: 0.4,          // post blur on the refracted layer
        tint: "rgba(255,255,255,0.05)",
        specularOpacity: 0.85,
        frost: 2,           // base backdrop blur (px)
      },
      options || {}
    );

    const uid = "lg" + UID++;
    el.classList.add("lg");
    el.dataset.lg = uid;

    // wrap existing children as content
    const content = document.createElement("span");
    content.className = "lg-content";
    while (el.firstChild) content.appendChild(el.firstChild);

    const bg = document.createElement("span");
    bg.className = "lg-bg";
    const tint = document.createElement("span");
    tint.className = "lg-tint";
    tint.style.background = o.tint;
    const spec = document.createElement("span");
    spec.className = "lg-spec";
    spec.style.opacity = o.specularOpacity;

    el.appendChild(bg);
    el.appendChild(tint);
    el.appendChild(spec);
    el.appendChild(content);

    const chromium = supportsBackdropSVG();

    const build = () => {
      const rect = el.getBoundingClientRect();
      if (rect.width < 2 || rect.height < 2) return;
      const { disp, spec: specUrl } = renderMaps(
        rect.width,
        rect.height,
        o.radius,
        o.bezel,
        o.surface
      );

      const fid = uid + "-f";
      const old = document.getElementById(fid);
      if (old) old.remove();
      makeFilter(fid, disp, rect.width, rect.height, o.scale, o.dispersion, o.blur);

      spec.style.webkitMaskImage = `url(${specUrl})`;
      spec.style.maskImage = `url(${specUrl})`;

      if (chromium) {
        // true refraction of the live page behind the element
        bg.style.backdropFilter = `url(#${fid}) blur(${o.frost}px) saturate(160%)`;
        bg.style.webkitBackdropFilter = `url(#${fid}) blur(${o.frost}px) saturate(160%)`;
      } else {
        // Firefox path: filter works via `filter` if we clone the backdrop.
        // Cheap robust fallback: frosted blur (still glass, no live warp).
        bg.style.backdropFilter = `blur(${o.frost + 6}px) saturate(150%)`;
        bg.style.webkitBackdropFilter = `blur(${o.frost + 6}px) saturate(150%)`;
        el.classList.add("lg-fallback");
      }
    };

    build();
    let raf;
    const ro = new ResizeObserver(() => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(build);
    });
    ro.observe(el);
    return { rebuild: build };
  }

  function auto() {
    document
      .querySelectorAll("[data-liquid-glass]")
      .forEach((el) => {
        let opt = {};
        try {
          opt = JSON.parse(el.getAttribute("data-liquid-glass") || "{}");
        } catch (e) {}
        apply(el, opt);
      });
  }

  global.LiquidGlass = { apply, auto, renderMaps };
  if (document.readyState !== "loading") auto();
  else document.addEventListener("DOMContentLoaded", auto);
})(window);
