export type RawBBox =
  | [number, number, number, number]
  | { x0?: number; y0?: number; x1?: number; y1?: number }
  | { x_min?: number; y_min?: number; x_max?: number; y_max?: number }
  | { xmin?: number; ymin?: number; xmax?: number; ymax?: number }
  | { left?: number; top?: number; width?: number; height?: number }
  | { x?: number; y?: number; width?: number; height?: number }
  | any;

export interface ParsedBBox {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface NormalizedBBox {
  leftPct: number;
  topPct: number;
  widthPct: number;
  heightPct: number;
}

export interface PageDimensions {
  naturalWidth?: number;
  naturalHeight?: number;
  dpi?: number;
}

// PyMuPDF rendering constants
export const RENDER_DPI = 150;
export const PDF_BASE_DPI = 72;
export const DEFAULT_PAGE_WIDTH_PT = 595.32;
export const DEFAULT_PAGE_HEIGHT_PT = 841.92;

/**
 * Parses diverse raw bounding box input structures into standardized {x0, y0, x1, y1}
 */
export function parseBoundingBox(raw: RawBBox): ParsedBBox | null {
  if (!raw || typeof raw !== 'object') {
    return null;
  }

  let x0: number | undefined;
  let y0: number | undefined;
  let x1: number | undefined;
  let y1: number | undefined;

  if (Array.isArray(raw)) {
    if (raw.length >= 4 && raw.slice(0, 4).every(v => typeof v === 'number' && !isNaN(v))) {
      [x0, y0, x1, y1] = raw;
    } else {
      return null;
    }
  } else {
    // Check standard x0, y0, x1, y1
    if (typeof raw.x0 === 'number' && typeof raw.y0 === 'number' && typeof raw.x1 === 'number' && typeof raw.y1 === 'number') {
      x0 = raw.x0;
      y0 = raw.y0;
      x1 = raw.x1;
      y1 = raw.y1;
    }
    // Check x_min, y_min, x_max, y_max
    else if (typeof raw.x_min === 'number' && typeof raw.y_min === 'number' && typeof raw.x_max === 'number' && typeof raw.y_max === 'number') {
      x0 = raw.x_min;
      y0 = raw.y_min;
      x1 = raw.x_max;
      y1 = raw.y_max;
    }
    // Check xmin, ymin, xmax, ymax
    else if (typeof raw.xmin === 'number' && typeof raw.ymin === 'number' && typeof raw.xmax === 'number' && typeof raw.ymax === 'number') {
      x0 = raw.xmin;
      y0 = raw.ymin;
      x1 = raw.xmax;
      y1 = raw.ymax;
    }
    // Check left, top, width, height
    else if (typeof raw.left === 'number' && typeof raw.top === 'number' && typeof raw.width === 'number' && typeof raw.height === 'number') {
      x0 = raw.left;
      y0 = raw.top;
      x1 = raw.left + raw.width;
      y1 = raw.top + raw.height;
    }
    // Check x, y, width, height
    else if (typeof raw.x === 'number' && typeof raw.y === 'number' && typeof raw.width === 'number' && typeof raw.height === 'number') {
      x0 = raw.x;
      y0 = raw.y;
      x1 = raw.x + raw.width;
      y1 = raw.y + raw.height;
    } else {
      return null;
    }
  }

  if (x0 === undefined || y0 === undefined || x1 === undefined || y1 === undefined) {
    return null;
  }

  // Ensure x0 <= x1 and y0 <= y1
  const minX = Math.min(x0, x1);
  const maxX = Math.max(x0, x1);
  const minY = Math.min(y0, y1);
  const maxY = Math.max(y0, y1);

  return {
    x0: minX,
    y0: minY,
    x1: maxX,
    y1: maxY,
  };
}

/**
 * Normalizes bounding box coordinates into percentage (0..100) offsets.
 * Automatically handles PyMuPDF 72-DPI point coordinates rendered on 150-DPI images,
 * raw pixel coordinates, or normalized 0..1 coordinates for any document aspect ratio.
 */
export function normalizeBoundingBox(
  raw: RawBBox,
  dimensions?: PageDimensions
): NormalizedBBox | null {
  const parsed = parseBoundingBox(raw);
  if (!parsed) return null;

  const { x0, y0, x1, y1 } = parsed;

  // Case 1: Already normalized coordinates in 0..1 range
  if (x0 >= 0 && x1 <= 1.0 && y0 >= 0 && y1 <= 1.0 && (x1 > 0 || y1 > 0)) {
    const leftPct = Math.max(0, Math.min(100, x0 * 100));
    const topPct = Math.max(0, Math.min(100, y0 * 100));
    const widthPct = Math.max(0.5, Math.min(100 - leftPct, (x1 - x0) * 100));
    const heightPct = Math.max(0.5, Math.min(100 - topPct, (y1 - y0) * 100));

    return {
      leftPct,
      topPct,
      widthPct,
      heightPct,
    };
  }

  // Determine coordinate space (PDF points 72-DPI vs rendered image pixels)
  let pageWidth = DEFAULT_PAGE_WIDTH_PT;
  let pageHeight = DEFAULT_PAGE_HEIGHT_PT;

  if (dimensions?.naturalWidth && dimensions.naturalWidth > 0 && dimensions?.naturalHeight && dimensions.naturalHeight > 0) {
    const dpi = dimensions.dpi || RENDER_DPI;
    const dpiScale = dpi / PDF_BASE_DPI; // 150 / 72 ≈ 2.0833
    const pagePtWidth = dimensions.naturalWidth / dpiScale;
    const pagePtHeight = dimensions.naturalHeight / dpiScale;

    // Detect if bbox coordinates are in image pixel space or PDF point space
    if (x1 > pagePtWidth * 1.05 || y1 > pagePtHeight * 1.05) {
      // Pixel coordinates (0..naturalWidth, 0..naturalHeight)
      pageWidth = dimensions.naturalWidth;
      pageHeight = dimensions.naturalHeight;
    } else {
      // Standard PDF point coordinates (0..pagePtWidth, 0..pagePtHeight)
      pageWidth = pagePtWidth;
      pageHeight = pagePtHeight;
    }
  }

  const clampedX0 = Math.max(0, Math.min(pageWidth, x0));
  const clampedY0 = Math.max(0, Math.min(pageHeight, y0));
  const clampedX1 = Math.max(0, Math.min(pageWidth, x1));
  const clampedY1 = Math.max(0, Math.min(pageHeight, y1));

  const leftPct = (clampedX0 / pageWidth) * 100;
  const topPct = (clampedY0 / pageHeight) * 100;
  const widthPct = Math.max(0.5, Math.min(100 - leftPct, ((clampedX1 - clampedX0) / pageWidth) * 100));
  const heightPct = Math.max(0.5, Math.min(100 - topPct, ((clampedY1 - clampedY0) / pageHeight) * 100));

  return {
    leftPct,
    topPct,
    widthPct,
    heightPct,
  };
}
