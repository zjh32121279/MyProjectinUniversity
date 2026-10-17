import html2canvas from "html2canvas";
import jsPDF from "jspdf";

const PAGE_W = 297;
const PAGE_H = 210;
const PAGE_MARGIN_X = 10;
const HEADER_H = 14;
const FOOTER_H = 8;
const CONTENT_Y = 18;
const CONTENT_H = PAGE_H - CONTENT_Y - FOOTER_H - 4;
const CONTENT_W = PAGE_W - PAGE_MARGIN_X * 2;
const EXPORT_ATTR = "data-bf-pdf-export";
const EXPORT_KEY_ATTR = "data-bf-export-key";

const COLOR_PROPS = [
  "color",
  "background-color",
  "border-top-color",
  "border-right-color",
  "border-bottom-color",
  "border-left-color",
  "outline-color",
  "text-decoration-color",
  "caret-color",
  "column-rule-color",
  "fill",
  "stroke",
  "stop-color",
  "flood-color",
  "lighting-color",
];

const DECORATIVE_PROPS = [
  "box-shadow",
  "text-shadow",
  "background-image",
  "border-image-source",
  "filter",
  "backdrop-filter",
];

const UNSUPPORTED_COLOR_FN = /\b(?:oklch|oklab|lab|lch|color|color-mix)\(/i;

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function parseNumberToken(token: string, percentBase = 1) {
  const text = token.trim().toLowerCase();
  if (!text || text === "none") return 0;
  const value = Number.parseFloat(text);
  if (!Number.isFinite(value)) return null;
  return text.endsWith("%") ? (value / 100) * percentBase : value;
}

function parseHue(token: string) {
  const text = token.trim().toLowerCase();
  if (!text || text === "none") return 0;
  const value = Number.parseFloat(text);
  if (!Number.isFinite(value)) return null;
  if (text.endsWith("rad")) return value * (180 / Math.PI);
  if (text.endsWith("turn")) return value * 360;
  if (text.endsWith("grad")) return value * 0.9;
  return value;
}

function parseAlpha(token: string | undefined) {
  if (!token) return 1;
  const value = parseNumberToken(token);
  return value === null ? 1 : clamp(value, 0, 1);
}

function splitColorBody(raw: string) {
  const parts = raw.replace(/,/g, " ").replace(/\s*\/\s*/g, " / ").trim().split(/\s+/).filter(Boolean);
  const slashIndex = parts.indexOf("/");
  return {
    channels: slashIndex >= 0 ? parts.slice(0, slashIndex) : parts,
    alpha: slashIndex >= 0 ? parts[slashIndex + 1] : undefined,
  };
}

function linearToSrgb(value: number) {
  const x = clamp(value, 0, 1);
  return x <= 0.0031308 ? 12.92 * x : 1.055 * Math.pow(x, 1 / 2.4) - 0.055;
}

function formatRgb(rLinear: number, gLinear: number, bLinear: number, alpha = 1) {
  const r = Math.round(linearToSrgb(rLinear) * 255);
  const g = Math.round(linearToSrgb(gLinear) * 255);
  const b = Math.round(linearToSrgb(bLinear) * 255);
  if (alpha < 1) return `rgba(${r}, ${g}, ${b}, ${Number(alpha.toFixed(3))})`;
  return `rgb(${r}, ${g}, ${b})`;
}

function oklabToRgb(l: number, a: number, b: number, alpha = 1) {
  const lPrime = l + 0.3963377774 * a + 0.2158037573 * b;
  const mPrime = l - 0.1055613458 * a - 0.0638541728 * b;
  const sPrime = l - 0.0894841775 * a - 1.2914855480 * b;

  const lmsL = lPrime ** 3;
  const lmsM = mPrime ** 3;
  const lmsS = sPrime ** 3;

  return formatRgb(
    4.0767416621 * lmsL - 3.3077115913 * lmsM + 0.2309699292 * lmsS,
    -1.2684380046 * lmsL + 2.6097574011 * lmsM - 0.3413193965 * lmsS,
    -0.0041960863 * lmsL - 0.7034186147 * lmsM + 1.7076147010 * lmsS,
    alpha,
  );
}

function parseOklch(raw: string) {
  const { channels, alpha } = splitColorBody(raw);
  if (channels.length < 3) return null;
  const l = parseNumberToken(channels[0]);
  const c = parseNumberToken(channels[1]);
  const h = parseHue(channels[2]);
  if (l === null || c === null || h === null) return null;
  const radians = (h * Math.PI) / 180;
  return oklabToRgb(l, c * Math.cos(radians), c * Math.sin(radians), parseAlpha(alpha));
}

function parseOklab(raw: string) {
  const { channels, alpha } = splitColorBody(raw);
  if (channels.length < 3) return null;
  const l = parseNumberToken(channels[0]);
  const a = parseNumberToken(channels[1]);
  const b = parseNumberToken(channels[2]);
  if (l === null || a === null || b === null) return null;
  return oklabToRgb(l, a, b, parseAlpha(alpha));
}

function replaceModernColorFunctions(value: string, fallback: string) {
  return value
    .replace(/oklch\(([^)]*)\)/gi, (_match, body: string) => parseOklch(body) ?? fallback)
    .replace(/oklab\(([^)]*)\)/gi, (_match, body: string) => parseOklab(body) ?? fallback)
    .replace(/\b(?:color-mix|lab|lch|color)\((?:[^()]|\([^()]*\))*\)/gi, fallback);
}

function fallbackForProperty(prop: string) {
  if (prop === "background-color") return "rgba(255, 255, 255, 0)";
  if (prop.includes("border") || prop === "outline-color" || prop === "column-rule-color") return "rgb(226, 232, 240)";
  return "rgb(15, 23, 42)";
}

function safeComputedValue(prop: string, value: string) {
  if (!value) return "";
  const replaced = replaceModernColorFunctions(value, fallbackForProperty(prop));
  if (!UNSUPPORTED_COLOR_FN.test(replaced)) return replaced;
  if (DECORATIVE_PROPS.includes(prop)) return "none";
  return fallbackForProperty(prop);
}

function sanitizeCloneStyleTags(clonedDoc: Document) {
  for (const style of Array.from(clonedDoc.querySelectorAll("style"))) {
    const text = style.textContent;
    if (!text || !UNSUPPORTED_COLOR_FN.test(text)) continue;
    style.textContent = replaceModernColorFunctions(text, "rgb(15, 23, 42)");
  }
}

function appendExportOverrides(clonedDoc: Document, cloneRoot: HTMLElement) {
  cloneRoot.setAttribute(EXPORT_ATTR, "true");
  const style = clonedDoc.createElement("style");
  style.textContent = `
    [${EXPORT_ATTR}], [${EXPORT_ATTR}] * {
      color-scheme: light !important;
      animation: none !important;
      transition: none !important;
    }
    [${EXPORT_ATTR}] *::before, [${EXPORT_ATTR}] *::after {
      color: rgb(15, 23, 42) !important;
      background: transparent !important;
      border-color: transparent !important;
      box-shadow: none !important;
      text-shadow: none !important;
    }
  `;
  clonedDoc.head.appendChild(style);
}

function inlineExportSafeStyles(element: HTMLElement, cloneRoot: HTMLElement) {
  const origAll = [element, ...Array.from(element.querySelectorAll("*"))];
  const cloneAll = [cloneRoot, ...Array.from(cloneRoot.querySelectorAll("*"))];

  for (let i = 0; i < origAll.length && i < cloneAll.length; i++) {
    const orig = origAll[i] as HTMLElement;
    const clone = cloneAll[i] as HTMLElement;
    if (!orig || !clone) continue;

    const cs = window.getComputedStyle(orig);
    for (const prop of COLOR_PROPS) {
      const value = safeComputedValue(prop, cs.getPropertyValue(prop));
      if (value) clone.style.setProperty(prop, value, "important");
    }
    for (const prop of DECORATIVE_PROPS) {
      const value = safeComputedValue(prop, cs.getPropertyValue(prop));
      if (value) clone.style.setProperty(prop, value, "important");
    }
    clone.style.setProperty("animation", "none", "important");
    clone.style.setProperty("transition", "none", "important");
  }
}

function exportPages(element: HTMLElement) {
  const pages = Array.from(element.querySelectorAll<HTMLElement>("[data-export-page]"));
  return pages.length ? pages : [element];
}

async function captureExportPage(page: HTMLElement, index: number) {
  const exportKey = `bookflow-export-page-${Date.now()}-${index}`;
  page.setAttribute(EXPORT_KEY_ATTR, exportKey);

  try {
    const rect = page.getBoundingClientRect();
    const width = Math.ceil(page.scrollWidth || rect.width);
    const height = Math.ceil(page.scrollHeight || rect.height);

    return await html2canvas(page, {
      scale: 3,
      useCORS: true,
      backgroundColor: "#ffffff",
      logging: false,
      width,
      height,
      windowWidth: Math.max(document.documentElement.clientWidth, width),
      windowHeight: Math.max(document.documentElement.clientHeight, height),
      onclone(clonedDoc: Document) {
        const cloneRoot = clonedDoc.querySelector<HTMLElement>(`[${EXPORT_KEY_ATTR}="${exportKey}"]`);
        if (!cloneRoot) return;
        sanitizeCloneStyleTags(clonedDoc);
        appendExportOverrides(clonedDoc, cloneRoot);
        inlineExportSafeStyles(page, cloneRoot);
      },
    });
  } finally {
    page.removeAttribute(EXPORT_KEY_ATTR);
  }
}

function drawPageChrome(pdf: jsPDF, date: string, pageIndex: number, pageCount: number, title: string) {
  pdf.setFillColor(248, 250, 252);
  pdf.rect(0, 0, PAGE_W, HEADER_H, "F");
  pdf.setFontSize(12);
  pdf.setTextColor(15, 23, 42);
  pdf.text(`BookFlow Data Center - ${title || "report"}`, PAGE_MARGIN_X, 9);
  pdf.setFontSize(8);
  pdf.setTextColor(100, 116, 139);
  pdf.text(date, PAGE_W - PAGE_MARGIN_X, 9, { align: "right" });
  pdf.text(`Page ${pageIndex + 1} / ${pageCount}`, PAGE_W - PAGE_MARGIN_X, PAGE_H - 5, { align: "right" });
  pdf.text(`BookFlow Data Center | ${date}`, PAGE_MARGIN_X, PAGE_H - 5);
}

function addCanvasPage(pdf: jsPDF, canvas: HTMLCanvasElement, date: string, pageIndex: number, pageCount: number, title: string) {
  if (pageIndex > 0) pdf.addPage();
  drawPageChrome(pdf, date, pageIndex, pageCount, title);

  let imgW = CONTENT_W;
  let imgH = (canvas.height * imgW) / canvas.width;
  if (imgH > CONTENT_H) {
    imgH = CONTENT_H;
    imgW = (canvas.width * imgH) / canvas.height;
  }

  const x = (PAGE_W - imgW) / 2;
  const y = CONTENT_Y + Math.max(0, (CONTENT_H - imgH) / 2);
  pdf.addImage(canvas.toDataURL("image/jpeg", 0.96), "JPEG", x, y, imgW, imgH, undefined, "FAST");
}

export async function buildDataCenterPDF(element: HTMLElement): Promise<void> {
  await new Promise((r) => setTimeout(r, 1500));
  const date = new Date().toISOString().slice(0, 10);
  const pages = exportPages(element);
  const pdf = new jsPDF({ orientation: "landscape", unit: "mm", format: "a4" });

  for (let index = 0; index < pages.length; index += 1) {
    const page = pages[index];
    const canvas = await captureExportPage(page, index);
    addCanvasPage(pdf, canvas, date, index, pages.length, page.dataset.exportTitle || `section-${index + 1}`);
  }

  pdf.save(`bookflow-data-${date}.pdf`);
}
