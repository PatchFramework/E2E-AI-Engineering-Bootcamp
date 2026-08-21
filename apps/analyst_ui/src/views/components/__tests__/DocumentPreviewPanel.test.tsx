import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DocumentPreviewPanel } from '../DocumentPreviewPanel';


describe('DocumentPreviewPanel', () => {
  const defaultProps = {
    documentId: 101,
    documentName: 'Apple_2025_10K.pdf',
    s3Path: 'filings/1/2025_FY/doc_101.pdf',
    pageNumber: 42,
    displayedPageNumber: '42',
    sectionPath: 'Financial Statements > Notes > Note 8. Debt',
    section: 'Note 8. Debt',
    boundingBox: [50, 100, 500, 250],
    snippet: 'Total term debt outstanding was $95.3 billion as of September 2025.',
    concept: 'Total Debt',
    availableDocuments: [
      {
        documentId: 101,
        filename: 'Apple_2025_10K.pdf',
        fiscalYear: 2025,
        fiscalPeriod: 'FY',
        pageNumbers: [42, 45],
      },
      {
        documentId: 100,
        filename: 'Apple_2024_10K.pdf',
        fiscalYear: 2024,
        fiscalPeriod: 'FY',
        pageNumbers: [38],
      },
    ],
    onSelectDocument: vi.fn(),
    onPageChange: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    // Mock scrollIntoView
    Element.prototype.scrollIntoView = vi.fn();
  });

  it('renders section hierarchy breadcrumbs at top of page', () => {
    render(<DocumentPreviewPanel {...defaultProps} />);
    expect(screen.getByText('Financial Statements')).toBeInTheDocument();
    expect(screen.getByText('Note 8. Debt')).toBeInTheDocument();
  });

  it('renders direct link to entire original document from S3', () => {
    render(<DocumentPreviewPanel {...defaultProps} />);
    const fullDocLink = screen.getByRole('link', { name: /full pdf|full document/i });
    expect(fullDocLink).toBeInTheDocument();
    expect(fullDocLink).toHaveAttribute('href', expect.stringContaining('/documents/101/file'));
    expect(fullDocLink).toHaveAttribute('target', '_blank');
  });

  it('renders multi-document selector tabs when multiple documents are present', () => {
    render(<DocumentPreviewPanel {...defaultProps} />);
    expect(screen.getByText('Apple_2025_10K.pdf')).toBeInTheDocument();
    expect(screen.getByText('Apple_2024_10K.pdf')).toBeInTheDocument();

    const secondDocButton = screen.getByText('Apple_2024_10K.pdf');
    fireEvent.click(secondDocButton);
    expect(defaultProps.onSelectDocument).toHaveBeenCalledWith(100, 38);
  });

  it('renders bounding box highlight overlay with concept badge', () => {
    render(<DocumentPreviewPanel {...defaultProps} />);
    const highlightBox = screen.getByTestId('bbox-highlight');
    expect(highlightBox).toBeInTheDocument();
    expect(screen.getByText('Total Debt')).toBeInTheDocument();
  });

  it('renders text snippet card with cited text', () => {
    render(<DocumentPreviewPanel {...defaultProps} />);
    expect(
      screen.getByText(/Total term debt outstanding was \$95\.3 billion/i)
    ).toBeInTheDocument();
  });

  it('handles page navigation controls (previous, next)', () => {
    render(<DocumentPreviewPanel {...defaultProps} />);
    const prevBtn = screen.getByTitle(/previous page/i);
    const nextBtn = screen.getByTitle(/next page/i);

    fireEvent.click(prevBtn);
    expect(defaultProps.onPageChange).toHaveBeenCalledWith(41);

    fireEvent.click(nextBtn);
    expect(defaultProps.onPageChange).toHaveBeenCalledWith(43);
  });

  it('handles zoom in, zoom out, and reset controls', () => {
    render(<DocumentPreviewPanel {...defaultProps} />);
    const zoomInBtn = screen.getByTitle(/zoom in/i);
    const zoomOutBtn = screen.getByTitle(/zoom out/i);
    const resetZoomBtn = screen.getByTitle(/reset zoom/i);

    expect(zoomInBtn).toBeInTheDocument();
    expect(zoomOutBtn).toBeInTheDocument();
    expect(resetZoomBtn).toBeInTheDocument();

    fireEvent.click(zoomInBtn);
    fireEvent.click(resetZoomBtn);
  });

  it('renders empty state placeholder when no document is linked', () => {
    render(
      <DocumentPreviewPanel
        {...defaultProps}
        documentId={null}
        documentName={null}
      />
    );
    expect(screen.getByText(/no document linked/i)).toBeInTheDocument();
  });
});
