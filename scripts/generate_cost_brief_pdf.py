"""Generate Clean Black & White Technical AWS Architecture Specification PDF.
Strictly: Inventory Comparison and Technical Rationale Table only.
"""
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

OUTPUT_PDF = Path(r"c:\Users\USER\Downloads\Prototype\Documentation\AWS_Cost_Strategy_Executive_Brief.pdf")
OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)

def build_pdf():
    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Pure Monochrome Palette
    c_black = colors.HexColor("#000000")
    c_dark = colors.HexColor("#222222")
    c_mid = colors.HexColor("#555555")
    c_light_bg = colors.HexColor("#F5F5F5")
    c_alt_bg = colors.HexColor("#FAFAFA")
    c_border = colors.HexColor("#CCCCCC")

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=c_black,
    )
    
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=c_mid,
    )

    header_meta_style = ParagraphStyle(
        "HeaderMeta",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11,
        textColor=c_black,
        alignment=2,
    )

    summary_box_style = ParagraphStyle(
        "SummaryText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12.5,
        textColor=c_dark,
    )

    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=c_black,
        spaceBefore=10,
        spaceAfter=4,
    )

    th_style = ParagraphStyle(
        "TH",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=c_black,
    )

    td_style = ParagraphStyle(
        "TD",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10.5,
        textColor=c_dark,
    )

    td_bold = ParagraphStyle(
        "TDBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=10.5,
        textColor=c_black,
    )

    story = []

    # 1. Header (Black & White)
    header_data = [
        [
            Paragraph("<b>DataLink Engine — AWS Infrastructure Architecture</b>", title_style),
            Paragraph("<b>Target Region: me-central-1 (UAE)</b><br/><b>Standard: UAE PDPL Compliant</b>", header_meta_style),
        ],
        [
            Paragraph("Technical Architecture Comparison: Full Enterprise Scope vs. Lean Core Setup", subtitle_style),
            Paragraph("", header_meta_style),
        ]
    ]
    h_table = Table(header_data, colWidths=[370, 170])
    h_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    story.append(h_table)
    story.append(HRFlowable(width="100%", thickness=1.5, color=c_black, spaceBefore=4, spaceAfter=8))

    # 2. Executive Overview Box
    summary_text = [
        [Paragraph("<b>ARCHITECTURAL ASSESSMENT & SCOPE REFINEMENT</b>", ParagraphStyle("H", parent=th_style, fontSize=8.5, leading=11))],
        [Paragraph(
            "An audit of the initial architecture blueprint identified several enterprise middleware layers (Aurora Serverless idle clusters, dedicated NAT Gateways, RDS Connection Proxies, and AWS WAF) that add operational complexity without benefiting the core workload at this stage. By streamlining to an essential, right-sized infrastructure (standard RDS PostgreSQL, ECS Fargate on Graviton, direct S3 Presigned uploads, and SQS messaging), we retain 100% of data processing, deduplication, full-text search, and UAE residency capabilities while maintaining a simpler, more maintainable stack.",
            summary_box_style
        )]
    ]
    sum_table = Table(summary_text, colWidths=[540])
    sum_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), c_light_bg),
        ("BOX", (0, 0), (-1, -1), 1, c_border),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(sum_table)
    story.append(Spacer(1, 8))

    # 3. Two-Column List: What Was Included Before vs. What We Are Using Now
    story.append(Paragraph("<b>1. Infrastructure Inventory Comparison</b>", section_heading))

    before_list = (
        "• <b>Amazon Aurora PostgreSQL (Serverless v2)</b><br/>"
        "• <b>AWS RDS Proxy</b> (Connection pooling layer)<br/>"
        "• <b>Dedicated Multi-AZ NAT Gateways</b><br/>"
        "• <b>Multi-AZ ECS Fargate Cluster</b> (Redundant pods)<br/>"
        "• <b>AWS WAF</b> (Managed Web Application Firewall)<br/>"
        "• <b>Amazon S3 Ingest & Export Buckets</b> (SSE-KMS)<br/>"
        "• <b>Amazon SQS & Dead Letter Queue (DLQ)</b><br/>"
        "• <b>AWS CloudFront CDN & Route 53 DNS</b><br/>"
        "• <b>AWS Secrets Manager & CloudWatch Alarms</b>"
    )

    now_list = (
        "• <b>Amazon RDS PostgreSQL (db.t4g.micro / small)</b><br/>"
        "• <b>SQLAlchemy Client Connection Pool</b> (In-app)<br/>"
        "• <b>VPC Security Groups & Gateway Endpoints</b> (Direct)<br/>"
        "• <b>Right-Sized ECS Fargate Task</b> (FastAPI + Worker)<br/>"
        "• <b>Native FastAPI Throttling & Validation</b> (In-app)<br/>"
        "• <b>Amazon S3 Direct Ingest via Presigned URLs</b><br/>"
        "• <b>Amazon SQS Ingestion Queue</b><br/>"
        "• <b>AWS CloudFront CDN & Route 53 DNS</b><br/>"
        "• <b>AWS Secrets Manager & Basic CloudWatch Logs</b>"
    )

    inv_data = [
        [
            Paragraph("<b>INITIAL ENTERPRISE ARCHITECTURE</b>", th_style),
            Paragraph("<b>OPTIMIZED ESSENTIALS ARCHITECTURE</b>", th_style)
        ],
        [
            Paragraph(before_list, td_style),
            Paragraph(now_list, td_style)
        ]
    ]
    inv_table = Table(inv_data, colWidths=[270, 270])
    inv_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_light_bg),
        ("GRID", (0, 0), (-1, -1), 0.5, c_border),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(inv_table)
    story.append(Spacer(1, 8))

    # 4. Detailed Component Rationale Table
    story.append(Paragraph("<b>2. Component-by-Component Technical Rationale</b>", section_heading))

    comp_rows = [
        [
            Paragraph("Layer", th_style),
            Paragraph("Previous Approach", th_style),
            Paragraph("Optimized Essential Approach", th_style),
            Paragraph("Technical Rationale", th_style)
        ],
        [
            Paragraph("<b>Database</b>", td_bold),
            Paragraph("Aurora Serverless v2", td_style),
            Paragraph("<b>Amazon RDS PostgreSQL (t4g.micro)</b>", td_style),
            Paragraph("Uses the same PostgreSQL engine. Retains full GIN trigram indexing for instant search.", td_style)
        ],
        [
            Paragraph("<b>Networking</b>", td_bold),
            Paragraph("Dedicated NAT Gateways", td_style),
            Paragraph("<b>VPC Endpoints (S3 & SQS)</b>", td_style),
            Paragraph("Containers communicate directly with S3 and SQS through AWS internal networking without internet traversal.", td_style)
        ],
        [
            Paragraph("<b>Compute / API</b>", td_bold),
            Paragraph("Multi-Pod ECS Fargate", td_style),
            Paragraph("<b>ECS Fargate on ARM64 Graviton</b>", td_style),
            Paragraph("Hosts FastAPI REST API and async Python worker in a single right-sized container on high-efficiency ARM cores.", td_style)
        ],
        [
            Paragraph("<b>Job Queue</b>", td_bold),
            Paragraph("Managed RabbitMQ/MSK", td_style),
            Paragraph("<b>Amazon SQS Queue</b>", td_style),
            Paragraph("Fully managed, zero-maintenance durable queue buffering incoming batch spreadsheet processing jobs.", td_style)
        ],
        [
            Paragraph("<b>File Uploads</b>", td_bold),
            Paragraph("Backend API Proxying", td_style),
            Paragraph("<b>Amazon S3 Presigned Direct Uploads</b>", td_style),
            Paragraph("Browsers stream files directly to S3, preventing API container memory spikes and timeouts on large files.", td_style)
        ],
        [
            Paragraph("<b>Frontend UI</b>", td_bold),
            Paragraph("Dedicated Web Servers", td_style),
            Paragraph("<b>Amazon S3 + CloudFront CDN</b>", td_style),
            Paragraph("Serverless React SPA edge delivery; sub-50ms loading times with global HTTPS termination.", td_style)
        ],
        [
            Paragraph("<b>App Security</b>", td_bold),
            Paragraph("AWS WAF + RDS Proxy", td_style),
            Paragraph("<b>FastAPI Middleware + Secrets Manager</b>", td_style),
            Paragraph("Rate limiting and SQL injection protections handled natively at the application and ORM levels.", td_style)
        ]
    ]

    comp_table = Table(comp_rows, colWidths=[70, 115, 145, 210])
    comp_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), c_light_bg),
        ("GRID", (0, 0), (-1, -1), 0.5, c_border),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, c_alt_bg]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(comp_table)

    doc.build(story)
    print(f"Successfully generated clean PDF at: {OUTPUT_PDF}")

if __name__ == "__main__":
    build_pdf()
