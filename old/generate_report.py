import csv
import html
import os
import argparse
from pathlib import Path

# Import QR code generation function
from qr_generator import generate_qr_code

def generate_html_report(base_url=None, source_csv="rdf_references.csv", output_html="reference_report.html"):
    # Create the HTML header
    html_header = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reference List</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
        }
        h1 {
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }
        .reference {
            margin-bottom: 20px;
            padding: 15px;
            border-radius: 5px;
            background-color: #f9f9f9;
            border-left: 4px solid #3498db;
        }
        .authors {
            font-weight: bold;
        }
        .title {
            font-style: italic;
        }
        .doi a {
            color: #3498db;
            text-decoration: none;
        }
        .doi a:hover {
            text-decoration: underline;
        }
        .date {
            color: #7f8c8d;
        }
        .no-doi {
            color: #e74c3c;
            font-style: italic;
        }
        .qr-container {
            margin-top: 30px;
            text-align: center;
        }
        .qr-container img {
            max-width: 200px;
            display: block;
            margin: 0 auto;
        }
        .source-info {
            text-align: center;
            font-size: 0.8em;
            color: #7f8c8d;
            margin-top: 20px;
            border-top: 1px solid #eee;
            padding-top: 10px;
        }
    </style>
</head>
<body>
    <h1>Reference List</h1>
    <div id="references">
"""

    # Create the HTML footer with source info
    source_name = os.path.basename(source_csv).split('_')[0].upper()  # extract RDF or BIB from filename
    html_footer = f"""
    </div>
    <div class="source-info">
        References sourced from {source_name} format
    </div>
</body>
</html>"""

    # Build the references section
    references_html = ""
    
    try:
        # Read the CSV file
        with open(source_csv, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            
            for row in reader:
                # Escape HTML special characters
                authors = html.escape(row.get('authors', ''))
                title = html.escape(row.get('title', ''))
                doi = html.escape(row.get('doi', ''))
                date_published = html.escape(row.get('date_published', ''))
                
                # Create HTML for this reference
                reference_html = "<div class=\"reference\">\n"
                reference_html += f"    <div class=\"authors\">{authors}</div>\n"
                reference_html += f"    <div class=\"title\">{title}</div>\n"
                
                if doi and doi.strip():
                    reference_html += f"    <div class=\"doi\">DOI: <a href=\"{doi}\" target=\"_blank\">{doi}</a></div>\n"
                else:
                    reference_html += "    <div class=\"no-doi\">No DOI available</div>\n"
                
                reference_html += f"    <div class=\"date\">Published: {date_published}</div>\n"
                reference_html += "</div>\n"
                
                references_html += reference_html
        
        # Generate the complete HTML
        complete_html = html_header + references_html + html_footer
        
        # Output file paths
        html_output_path = output_html
        qr_output_path = f"{os.path.splitext(output_html)[0]}_qr.png"
        
        # Write to file
        with open(html_output_path, 'w', encoding='utf-8') as f:
            f.write(complete_html)
        
        print(f"Report generated successfully: {html_output_path}")
        
        # Generate QR code for the HTML report
        if base_url:
            # Use the provided base URL (web hosting)
            url = f"{base_url.rstrip('/')}/{html_output_path}"
            generate_qr_code(url, qr_output_path, size=10)
            print(f"QR code generated for URL: {url}")
        else:
            # Fallback to local file path
            file_path = Path(html_output_path).resolve()
            file_url = f"file://{file_path}"
            generate_qr_code(file_url, qr_output_path, size=10)
            print(f"QR code generated for local file: {file_url}")
        
        print(f"QR code saved as: {qr_output_path}")
    
    except Exception as e:
        print(f"Error generating report: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate HTML reference report with QR code')
    parser.add_argument('--url', help='Base URL where the report will be hosted (e.g., https://example.com/reports/)')
    parser.add_argument('--source', default='rdf_references.csv', help='Source CSV file with references (default: rdf_references.csv)')
    parser.add_argument('--output', default='reference_report.html', help='Output HTML filename (default: reference_report.html)')
    args = parser.parse_args()
    
    generate_html_report(base_url=args.url, source_csv=args.source, output_html=args.output) 