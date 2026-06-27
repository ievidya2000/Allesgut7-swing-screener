"""Email notification system."""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.application import MIMEApplication
from email import encoders
from pathlib import Path

from screener_v2.config_email import load_email_config, is_email_configured

logger = logging.getLogger("notifications")


def send_email(subject, body, attachments=None, html=False):
    if not is_email_configured():
        logger.warning("Email not configured. Skipping notification.")
        return False

    config = load_email_config()

    try:
        msg = MIMEMultipart("mixed")
        msg["From"] = f"Swing Screener <{config['from_email']}>"
        msg["To"] = config["to_email"]
        msg["Subject"] = subject
        msg["Reply-To"] = config["from_email"]
        msg["X-Mailer"] = "Swing Screener v2"
        msg["X-Priority"] = "3"

        if html:
            msg.attach(MIMEText(body, "html"))
        else:
            msg.attach(MIMEText(body, "plain"))

        if attachments:
            for file_path in attachments:
                path = Path(file_path)
                if path.exists():
                    if path.suffix == '.csv':
                        with open(path, "r") as f:
                            csv_content = f.read()
                        part = MIMEText(csv_content, "csv")
                        part.add_header(
                            "Content-Disposition",
                            f"attachment; filename={path.name}"
                        )
                    else:
                        with open(path, "rb") as f:
                            part = MIMEBase("application", "octet-stream")
                            part.set_payload(f.read())
                        encoders.encode_base64(part)
                        part.add_header(
                            "Content-Disposition",
                            f"attachment; filename={path.name}"
                        )
                    msg.attach(part)

        with smtplib.SMTP(config["smtp_server"], config["smtp_port"]) as server:
            if config.get("use_tls"):
                server.starttls()
            server.login(config["smtp_username"], config["smtp_password"])
            server.send_message(msg)

        logger.info(f"Email sent: {subject}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


def send_daily_summary_email(summary, report_text, attachments=None):
    subject = f"[Swing Screener] Daily Summary - {summary['date']}"

    today_trades = summary.get('today_trade_details', [])
    trades_rows = ""
    for t in today_trades:
        color = "#2ecc71" if t.get('return_pct', 0) > 0 else "#e74c3c"
        trades_rows += f"""
        <tr>
            <td style="padding: 8px; border: 1px solid #ddd;">{t['ticker']}</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{t.get('setup', 'N/A')}</td>
            <td style="padding: 8px; border: 1px solid #ddd; color: {color}; font-weight: bold;">{t.get('return_pct', 0):+.2f}%</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{t.get('exit_reason', '')}</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{t.get('days_held', 0)}</td>
        </tr>
        """

    if not trades_rows:
        trades_rows = '<tr><td colspan="5" style="padding: 8px; border: 1px solid #ddd; text-align: center;">No trades closed today</td></tr>'

    html_body = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; }}
            .header {{ background-color: #2c3e50; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
            .content {{ background-color: #f9f9f9; padding: 20px; border: 1px solid #ddd; }}
            .section {{ margin-bottom: 20px; }}
            .section h3 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px; }}
            .metric {{ display: inline-block; width: 45%; margin: 5px; padding: 10px; background-color: white; border-radius: 5px; border: 1px solid #ddd; }}
            .metric-label {{ font-size: 12px; color: #666; }}
            .metric-value {{ font-size: 18px; font-weight: bold; color: #2c3e50; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th {{ background-color: #3498db; color: white; padding: 10px; border: 1px solid #ddd; }}
            .footer {{ background-color: #ecf0f1; padding: 10px; text-align: center; font-size: 12px; color: #666; border-radius: 0 0 5px 5px; }}
            .positive {{ color: #2ecc71; }}
            .negative {{ color: #e74c3c; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Daily Performance Summary</h1>
                <p>{summary['date']}</p>
            </div>

            <div class="content">
                <div class="section">
                    <h3>Today's Activity</h3>
                    <div class="metric">
                        <div class="metric-label">New Predictions</div>
                        <div class="metric-value">{summary['today_predictions']}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Trades Closed</div>
                        <div class="metric-value">{summary['today_trades_closed']}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Win Rate</div>
                        <div class="metric-value {'positive' if summary['today_win_rate'] >= 0.5 else 'negative'}">{summary['today_win_rate']:.1%}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Avg Return</div>
                        <div class="metric-value {'positive' if summary['today_avg_return'] >= 0 else 'negative'}">{summary['today_avg_return']:+.2f}%</div>
                    </div>
                </div>

                <div class="section">
                    <h3>Recent Performance (7 days)</h3>
                    <div class="metric">
                        <div class="metric-label">Trades</div>
                        <div class="metric-value">{summary['recent_trades']}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Win Rate</div>
                        <div class="metric-value {'positive' if summary['recent_win_rate'] >= 0.5 else 'negative'}">{summary['recent_win_rate']:.1%}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Avg Return</div>
                        <div class="metric-value {'positive' if summary['recent_avg_return'] >= 0 else 'negative'}">{summary['recent_avg_return']:+.2f}%</div>
                    </div>
                </div>

                <div class="section">
                    <h3>Overall Status</h3>
                    <div class="metric">
                        <div class="metric-label">Total Predictions</div>
                        <div class="metric-value">{summary['total_predictions']:,}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Pending</div>
                        <div class="metric-value">{summary['pending']:,}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Active</div>
                        <div class="metric-value">{summary['active']:,}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Closed</div>
                        <div class="metric-value">{summary['closed']:,}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Win Rate</div>
                        <div class="metric-value {'positive' if summary['overall_win_rate'] >= 0.5 else 'negative'}">{summary['overall_win_rate']:.1%}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Avg Return</div>
                        <div class="metric-value {'positive' if summary['overall_avg_return'] >= 0 else 'negative'}">{summary['overall_avg_return']:+.2f}%</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Profit Factor</div>
                        <div class="metric-value">{summary['overall_profit_factor']:.2f}</div>
                    </div>
                </div>

                <div class="section">
                    <h3>Today's Closed Trades</h3>
                    <table>
                        <tr>
                            <th>Ticker</th>
                            <th>Setup</th>
                            <th>Return</th>
                            <th>Reason</th>
                            <th>Days</th>
                        </tr>
                        {trades_rows}
                    </table>
                </div>
            </div>

            <div class="footer" style="background: linear-gradient(135deg, #FF6B35 0%, #FF4444 100%); padding: 15px; border-radius: 8px; text-align: center;">
                <p style="color: white; font-weight: bold; font-size: 14px; margin: 0;">
                    ⚠️ Think First. Trade Second. DYOR - Do Your Own Research
                </p>
                <p style="color: #ddd; font-size: 12px; margin: 8px 0 0 0;">
                    Swing Screener v2 - Automated Daily Report
                </p>
                <p style="color: #ddd; font-size: 12px; margin: 4px 0 0 0;">
                    Full report attached as CSV
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    return send_email(subject, html_body, attachments, html=True)


def send_archive_email(archive_path, csv_path, period):
    subject = f"[Swing Screener] Performance Archive - {period}"

    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif;">
        <h2>Performance Archive</h2>
        <p>Period: {period}</p>
        <p>Attached files:</p>
        <ul>
            <li>{Path(archive_path).name} (JSON)</li>
            <li>{Path(csv_path).name} (CSV)</li>
        </ul>
        <p>This is an automated archive generated after 90 days retention.</p>
    </body>
    </html>
    """

    return send_email(subject, body, [archive_path, csv_path], html=True)
