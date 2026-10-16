import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';

export interface ExportPdfOptions {
  element: HTMLElement;
  reportTitle?: string;
  brandName?: string;
  agentName?: string;
  fileName?: string;
}

/**
 * Exports an HTML element containing a rendered report (markdown, tables, Recharts)
 * to a clean, multi-page, high-resolution PDF document.
 */
export async function exportReportToPdf({
  element,
  reportTitle = 'Strategic Intelligence Report',
  brandName,
  agentName,
  fileName,
}: ExportPdfOptions): Promise<void> {
  if (!element) {
    throw new Error('No element provided for PDF export');
  }

  // 1. Create off-screen clone container for print layout
  const printWrapper = document.createElement('div');
  printWrapper.setAttribute('id', 'stratai-pdf-export-wrapper');
  printWrapper.style.position = 'fixed';
  printWrapper.style.left = '-9999px';
  printWrapper.style.top = '0';
  printWrapper.style.width = '820px';
  printWrapper.style.backgroundColor = '#FFFFFF';
  printWrapper.style.color = '#1A1A1A';
  printWrapper.style.fontFamily = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
  printWrapper.style.padding = '36px 44px';
  printWrapper.style.boxSizing = 'border-box';
  printWrapper.style.zIndex = '-9999';

  // 2. Build Executive Cover / Report Header
  const dateStr = new Date().toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });

  const displayBrand = brandName || 'StratAI Intelligence';
  const displayTitle = reportTitle || agentName || 'Strategic Intelligence Report';

  const headerDiv = document.createElement('div');
  headerDiv.style.marginBottom = '28px';
  headerDiv.style.borderBottom = '2px solid #E8E4DC';
  headerDiv.style.paddingBottom = '20px';
  headerDiv.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px;">
      <div style="display: flex; align-items: center; gap: 10px;">
        <div style="width: 32px; height: 32px; border-radius: 8px; background: linear-gradient(135deg, #2D2A26, #D4A843); display: flex; align-items: center; justify-content: center; color: #FFFFFF; font-weight: 800; font-size: 15px;">
          S
        </div>
        <div>
          <div style="font-size: 16px; font-weight: 800; color: #1A1A1A; letter-spacing: -0.02em;">StratAI</div>
          <div style="font-size: 11px; font-weight: 600; color: #D4A843; text-transform: uppercase; letter-spacing: 0.05em;">Strategic Market Intelligence</div>
        </div>
      </div>
      <div style="text-align: right;">
        <div style="font-size: 11px; font-weight: 600; color: #78716C; text-transform: uppercase; letter-spacing: 0.05em;">Generated Date</div>
        <div style="font-size: 12px; font-weight: 600; color: #1A1A1A;">${dateStr}</div>
      </div>
    </div>

    <div style="margin-top: 10px;">
      <div style="display: inline-block; background: #F5F1EB; color: #B45309; font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 6px; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.04em;">
        ${agentName ? `${agentName} Report` : 'Executive Strategy Document'}
      </div>
      <h1 style="font-size: 24px; font-weight: 800; color: #1A1A1A; margin: 0 0 6px 0; line-height: 1.3; letter-spacing: -0.02em;">
        ${displayTitle}
      </h1>
      <p style="font-size: 13px; color: #57534E; margin: 0; line-height: 1.5;">
        Prepared for <strong style="color: #1A1A1A;">${displayBrand}</strong> &bull; Powered by StratAI Multi-Agent Strategy Engine
      </p>
    </div>
  `;
  printWrapper.appendChild(headerDiv);

  // 3. Clone and clean content element
  const contentClone = element.cloneNode(true) as HTMLElement;

  // Enhance styles for print/PDF fidelity
  contentClone.style.fontSize = '13px';
  contentClone.style.lineHeight = '1.7';
  contentClone.style.color = '#1A1A1A';
  contentClone.style.overflow = 'visible';

  // Format tables to fit page cleanly
  const tableWrappers = contentClone.querySelectorAll('.tableWrapper, [class*="tableWrapper"]');
  tableWrappers.forEach((tw) => {
    (tw as HTMLElement).style.overflow = 'visible';
    (tw as HTMLElement).style.width = '100%';
    (tw as HTMLElement).style.margin = '16px 0';
    (tw as HTMLElement).style.boxShadow = 'none';
  });

  const tables = contentClone.querySelectorAll('table');
  tables.forEach((t) => {
    t.style.width = '100%';
    t.style.minWidth = '100%';
    t.style.fontSize = '11px';
    t.style.borderCollapse = 'collapse';
    t.style.tableLayout = 'auto';
  });

  const ths = contentClone.querySelectorAll('th');
  ths.forEach((th) => {
    th.style.backgroundColor = '#F5F1EB';
    th.style.color = '#1A1A1A';
    th.style.padding = '8px 10px';
    th.style.border = '1px solid #E8E4DC';
    th.style.fontSize = '11px';
    th.style.fontWeight = '700';
  });

  const tds = contentClone.querySelectorAll('td');
  tds.forEach((td) => {
    td.style.padding = '8px 10px';
    td.style.border = '1px solid #E8E4DC';
    td.style.fontSize = '11px';
    td.style.wordBreak = 'break-word';
    td.style.minWidth = '0';
  });

  // Replicate SVG dimensions for Recharts
  const originalSvgs = element.querySelectorAll('svg');
  const cloneSvgs = contentClone.querySelectorAll('svg');
  originalSvgs.forEach((origSvg, idx) => {
    const cloneSvg = cloneSvgs[idx];
    if (cloneSvg) {
      const bbox = origSvg.getBoundingClientRect();
      if (bbox.width > 0 && bbox.height > 0) {
        cloneSvg.setAttribute('width', `${Math.round(bbox.width)}`);
        cloneSvg.setAttribute('height', `${Math.round(bbox.height)}`);
      }
    }
  });

  printWrapper.appendChild(contentClone);
  document.body.appendChild(printWrapper);

  try {
    // 4. Render to high-res canvas (scale: 2 for crisp 300dpi-equivalent print)
    const canvas = await html2canvas(printWrapper, {
      scale: 2,
      useCORS: true,
      logging: false,
      backgroundColor: '#FFFFFF',
      windowWidth: 820,
    });

    // 5. Paginate onto A4 PDF document
    const pdf = new jsPDF({
      orientation: 'portrait',
      unit: 'mm',
      format: 'a4',
    });

    const pdfPageWidth = 210;
    const pdfPageHeight = 297;
    const marginX = 14;
    const marginTop = 18;
    const marginBottom = 18;

    const printableWidthMm = pdfPageWidth - marginX * 2; // 182mm
    const printableHeightMm = pdfPageHeight - marginTop - marginBottom; // 261mm

    const scale = 2; // canvas scale
    const pxToMm = printableWidthMm / (printWrapper.offsetWidth * scale);
    const maxPageCanvasHeight = Math.floor(printableHeightMm / pxToMm);

    // Collect DOM elements relative positions to avoid slicing inside elements
    const wrapperRect = printWrapper.getBoundingClientRect();
    const leafBlocks = printWrapper.querySelectorAll('h1, h2, h3, h4, p, li, tr, blockquote, pre, [class*="recharts"]');
    const blockIntervals: Array<{ top: number; bottom: number; isHeading: boolean; isChart: boolean }> = [];

    leafBlocks.forEach((el) => {
      const rect = el.getBoundingClientRect();
      const top = (rect.top - wrapperRect.top) * scale;
      const bottom = (rect.bottom - wrapperRect.top) * scale;
      const tag = el.tagName.toLowerCase();
      const isHeading = ['h1', 'h2', 'h3', 'h4'].includes(tag);
      const isChart = el.className ? String(el.className).includes('recharts') : false;
      blockIntervals.push({ top, bottom, isHeading, isChart });
    });

    let currentY = 0;
    let pageNumber = 1;
    const pageCuts: Array<{ startY: number; endY: number }> = [];

    while (currentY < canvas.height) {
      const targetEndY = currentY + maxPageCanvasHeight;

      if (targetEndY >= canvas.height) {
        // Fits on final page
        pageCuts.push({ startY: currentY, endY: canvas.height });
        break;
      }

      // Find safe cut point: avoid straddling charts, headings, table rows
      let safeCutY = targetEndY;
      const minAcceptableY = currentY + maxPageCanvasHeight * 0.6; // don't make page shorter than 60%

      for (const block of blockIntervals) {
        // Straddles cut line
        if (block.top < targetEndY && block.bottom > targetEndY) {
          if (block.top >= minAcceptableY) {
            safeCutY = Math.min(safeCutY, block.top);
          }
        }
        // Avoid orphan headings right near the bottom (within 40px)
        if (block.isHeading && block.top < targetEndY && block.top > targetEndY - 80 * scale) {
          if (block.top >= minAcceptableY) {
            safeCutY = Math.min(safeCutY, block.top);
          }
        }
      }

      // Add small breathing margin before block (e.g. 4px)
      safeCutY = Math.max(minAcceptableY, safeCutY - 6);
      pageCuts.push({ startY: currentY, endY: safeCutY });
      currentY = safeCutY;
    }

    const totalPages = pageCuts.length;

    pageCuts.forEach((cut, pageIdx) => {
      if (pageIdx > 0) {
        pdf.addPage();
      }

      const sliceHeight = cut.endY - cut.startY;
      const sliceCanvas = document.createElement('canvas');
      sliceCanvas.width = canvas.width;
      sliceCanvas.height = sliceHeight;

      const sliceCtx = sliceCanvas.getContext('2d');
      if (sliceCtx) {
        sliceCtx.fillStyle = '#FFFFFF';
        sliceCtx.fillRect(0, 0, sliceCanvas.width, sliceHeight);
        sliceCtx.drawImage(
          canvas,
          0,
          cut.startY,
          canvas.width,
          sliceHeight,
          0,
          0,
          canvas.width,
          sliceHeight
        );

        const imgData = sliceCanvas.toDataURL('image/jpeg', 0.95);
        const renderHeightMm = sliceHeight * pxToMm;

        pdf.addImage(imgData, 'JPEG', marginX, marginTop, printableWidthMm, renderHeightMm);
      }

      // Top running header on pages 2+
      if (pageIdx > 0) {
        pdf.setFontSize(8);
        pdf.setTextColor(150, 145, 140);
        pdf.text('StratAI Strategic Intelligence Report', marginX, 10);
        pdf.text(displayBrand, pdfPageWidth - marginX, 10, { align: 'right' });
        pdf.setDrawColor(230, 225, 218);
        pdf.setLineWidth(0.3);
        pdf.line(marginX, 12, pdfPageWidth - marginX, 12);
      }

      // Running footer on all pages
      pdf.setFontSize(8);
      pdf.setTextColor(150, 145, 140);
      pdf.setDrawColor(230, 225, 218);
      pdf.setLineWidth(0.3);
      pdf.line(marginX, pdfPageHeight - 12, pdfPageWidth - marginX, pdfPageHeight - 12);

      pdf.text('Confidential & Proprietary \u2022 Generated by StratAI', marginX, pdfPageHeight - 7);
      pdf.text(`Page ${pageIdx + 1} of ${totalPages}`, pdfPageWidth - marginX, pdfPageHeight - 7, { align: 'right' });
    });

    // 6. Trigger download as brand_agent.pdf (e.g. unacademy_Competitive analysis.pdf)
    const sanitize = (s: string) => s.replace(/[/\\?%*:|"<>]/g, '').trim();
    let downloadName = fileName;
    if (!downloadName) {
      const cleanBrand = sanitize(displayBrand || 'Brand');
      const cleanAgent = sanitize(agentName || displayTitle || 'Strategy_Report');
      downloadName = `${cleanBrand}_${cleanAgent}.pdf`;
    } else if (!downloadName.toLowerCase().endsWith('.pdf')) {
      downloadName += '.pdf';
    }

    pdf.save(downloadName);
  } finally {
    // Cleanup temporary DOM container
    if (printWrapper && printWrapper.parentNode) {
      printWrapper.parentNode.removeChild(printWrapper);
    }
  }
}
