import { describe, it, expect } from 'vitest';
import {
  parseBoundingBox,
  normalizeBoundingBox,
  RawBBox,
  RENDER_DPI,
  PDF_BASE_DPI,
} from '../bboxUtils';

describe('bboxUtils', () => {
  describe('parseBoundingBox', () => {
    it('returns null for null, undefined, or empty values', () => {
      expect(parseBoundingBox(null)).toBeNull();
      expect(parseBoundingBox(undefined)).toBeNull();
      expect(parseBoundingBox([])).toBeNull();
      expect(parseBoundingBox({})).toBeNull();
      expect(parseBoundingBox('invalid')).toBeNull();
    });

    it('parses array format [x0, y0, x1, y1]', () => {
      const bbox: RawBBox = [50, 100, 500, 300];
      const parsed = parseBoundingBox(bbox);
      expect(parsed).toEqual({
        x0: 50,
        y0: 100,
        x1: 500,
        y1: 300,
      });
    });

    it('parses dict format with x0, y0, x1, y1', () => {
      const bbox: RawBBox = { x0: 10, y0: 20, x1: 200, y1: 150 };
      const parsed = parseBoundingBox(bbox);
      expect(parsed).toEqual({
        x0: 10,
        y0: 20,
        x1: 200,
        y1: 150,
      });
    });

    it('parses dict format with x_min, y_min, x_max, y_max', () => {
      const bbox: RawBBox = { x_min: 15.5, y_min: 25.5, x_max: 300.0, y_max: 400.0 };
      const parsed = parseBoundingBox(bbox);
      expect(parsed).toEqual({
        x0: 15.5,
        y0: 25.5,
        x1: 300.0,
        y1: 400.0,
      });
    });

    it('parses dict format with left, top, width, height', () => {
      const bbox: RawBBox = { left: 40, top: 80, width: 200, height: 100 };
      const parsed = parseBoundingBox(bbox);
      expect(parsed).toEqual({
        x0: 40,
        y0: 80,
        x1: 240,
        y1: 180,
      });
    });

    it('handles inverted coordinates gracefully (x1 < x0 or y1 < y0)', () => {
      const bbox: RawBBox = [500, 300, 50, 100];
      const parsed = parseBoundingBox(bbox);
      expect(parsed).toEqual({
        x0: 50,
        y0: 100,
        x1: 500,
        y1: 300,
      });
    });
  });

  describe('normalizeBoundingBox coordinate mapping & DPI conversion', () => {
    it('normalizes 0..1 normalized coordinates directly', () => {
      const raw: RawBBox = [0.1, 0.2, 0.8, 0.5];
      const normalized = normalizeBoundingBox(raw);
      expect(normalized).not.toBeNull();
      expect(normalized?.leftPct).toBeCloseTo(10, 1);
      expect(normalized?.topPct).toBeCloseTo(20, 1);
      expect(normalized?.widthPct).toBeCloseTo(70, 1);
      expect(normalized?.heightPct).toBeCloseTo(30, 1);
    });

    it('accurately converts standard 72-DPI PyMuPDF bbox on 150-DPI rendered A4 image', () => {
      // Standard A4 PDF page is 595.32 x 841.92 pt
      // Rendered image at 150 DPI is: 1240.25 x 1754.0 px
      const naturalWidth = Math.round(595.32 * (RENDER_DPI / PDF_BASE_DPI)); // 1240
      const naturalHeight = Math.round(841.92 * (RENDER_DPI / PDF_BASE_DPI)); // 1754

      // Block is at 10% left, 20% top, 80% width, 15% height in PDF points
      const x0 = 59.53;
      const y0 = 168.38;
      const x1 = 59.53 + 476.25; // width = 80%
      const y1 = 168.38 + 126.29; // height = 15%

      const raw: RawBBox = [x0, y0, x1, y1];
      const normalized = normalizeBoundingBox(raw, { naturalWidth, naturalHeight });

      expect(normalized).not.toBeNull();
      // Should correctly calculate 10% left, 20% top, 80% width, 15% height (NOT halved!)
      expect(normalized?.leftPct).toBeCloseTo(10, 0.5);
      expect(normalized?.topPct).toBeCloseTo(20, 0.5);
      expect(normalized?.widthPct).toBeCloseTo(80, 0.5);
      expect(normalized?.heightPct).toBeCloseTo(15, 0.5);
    });

    it('accurately converts 72-DPI PyMuPDF bbox on Landscape / Horizontal format image at 150 DPI', () => {
      // Landscape A4 PDF page is 841.92 x 595.32 pt
      const naturalWidth = Math.round(841.92 * (150 / 72)); // 1754
      const naturalHeight = Math.round(595.32 * (150 / 72)); // 1240

      // Block at 15% left, 25% top, 70% width, 20% height
      const x0 = 841.92 * 0.15;
      const y0 = 595.32 * 0.25;
      const x1 = x0 + 841.92 * 0.70;
      const y1 = y0 + 595.32 * 0.20;

      const raw: RawBBox = [x0, y0, x1, y1];
      const normalized = normalizeBoundingBox(raw, { naturalWidth, naturalHeight });

      expect(normalized).not.toBeNull();
      expect(normalized?.leftPct).toBeCloseTo(15, 0.5);
      expect(normalized?.topPct).toBeCloseTo(25, 0.5);
      expect(normalized?.widthPct).toBeCloseTo(70, 0.5);
      expect(normalized?.heightPct).toBeCloseTo(20, 0.5);
    });

    it('accurately converts US Letter format at 150 DPI (612 x 792 pt -> 1275 x 1650 px)', () => {
      const naturalWidth = 1275;
      const naturalHeight = 1650;

      const x0 = 61.2; // 10%
      const y0 = 79.2; // 10%
      const x1 = 61.2 + 489.6; // 80%
      const y1 = 79.2 + 316.8; // 40%

      const raw: RawBBox = [x0, y0, x1, y1];
      const normalized = normalizeBoundingBox(raw, { naturalWidth, naturalHeight });

      expect(normalized).not.toBeNull();
      expect(normalized?.leftPct).toBeCloseTo(10, 0.5);
      expect(normalized?.topPct).toBeCloseTo(10, 0.5);
      expect(normalized?.widthPct).toBeCloseTo(80, 0.5);
      expect(normalized?.heightPct).toBeCloseTo(40, 0.5);
    });

    it('supports pixel space coordinates (0..naturalWidth)', () => {
      const naturalWidth = 1200;
      const naturalHeight = 1600;

      const raw: RawBBox = [120, 160, 1080, 480];
      const normalized = normalizeBoundingBox(raw, { naturalWidth, naturalHeight });

      expect(normalized).not.toBeNull();
      expect(normalized?.leftPct).toBeCloseTo(10, 0.5);
      expect(normalized?.topPct).toBeCloseTo(10, 0.5);
      expect(normalized?.widthPct).toBeCloseTo(80, 0.5);
      expect(normalized?.heightPct).toBeCloseTo(20, 0.5);
    });

    it('clamps coordinates safely when out of bounds', () => {
      const naturalWidth = 1240;
      const naturalHeight = 1754;
      const raw: RawBBox = [-50, -20, 1500, 2000];
      const normalized = normalizeBoundingBox(raw, { naturalWidth, naturalHeight });

      expect(normalized).not.toBeNull();
      expect(normalized?.leftPct).toBe(0);
      expect(normalized?.topPct).toBe(0);
      expect((normalized?.leftPct ?? 0) + (normalized?.widthPct ?? 0)).toBeLessThanOrEqual(100);
      expect((normalized?.topPct ?? 0) + (normalized?.heightPct ?? 0)).toBeLessThanOrEqual(100);
    });
  });
});
