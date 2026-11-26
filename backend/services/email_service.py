"""
Email Service
=============
Handles dispatching transactional and invitation emails via SMTP
configured with Google App Password or standard SMTP relay.
"""

import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, List
from dotenv import load_dotenv

# Ensure .env is loaded from project root or backend dir
for _candidate in [
    os.path.join(os.getcwd(), ".env"),
    os.path.join(os.path.dirname(__file__), ".env"),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env")),
]:
    if os.path.exists(_candidate):
        load_dotenv(_candidate, override=False)

logger = logging.getLogger(__name__)

def _get_smtp_config():
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "ai@vichitraa.agency")
    password = os.getenv("SMTP_PASSWORD", "").replace(" ", "")
    email_from = os.getenv("EMAIL_FROM", user or "ai@vichitraa.agency")
    from_name = os.getenv("EMAIL_FROM_NAME", "StratAI")
    app_url = os.getenv("APP_URL") or os.getenv("NEXT_PUBLIC_APP_URL") or "http://localhost:3000"
    return host, port, user, password, email_from, from_name, app_url


def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
    from_name: Optional[str] = None,
) -> bool:
    """
    Sends an email to a single recipient using STARTTLS over SMTP.
    Returns True if sent successfully, False otherwise.
    """
    host, port, user, password, email_from, default_name, _ = _get_smtp_config()

    if not user or not password:
        logger.error("[email_service] SMTP_USER or SMTP_PASSWORD is not configured in environment.")
        return False

    sender_name = from_name or default_name
    sender_header = f"{sender_name} <{email_from}>"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender_header
    msg["To"] = to_email

    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        logger.info(f"[email_service] Connecting to {host}:{port} for recipient {to_email}...")
        server = smtplib.SMTP(host, port, timeout=15)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(user, password)
        server.sendmail(email_from, [to_email], msg.as_string())
        server.quit()
        logger.info(f"[email_service] Email successfully sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"[email_service] Failed to send email to {to_email}: {type(e).__name__}: {e}")
        return False


def build_invitation_html(
    inviter_name: str,
    inviter_email: str,
    chat_title: str,
    full_share_url: str,
    custom_message: Optional[str] = None,
) -> str:
    """Renders a warm, professional, minimal HTML email invitation for StratAI."""
    custom_msg_section = ""
    if custom_message and custom_message.strip():
        custom_msg_section = f"""
        <div style="background: #FAF8F5; border-left: 3px solid #D4A843; padding: 12px 16px; margin: 20px 0; border-radius: 4px; font-style: italic; color: #4B453E; font-size: 14px; line-height: 1.5;">
            "{custom_message.strip()}"
        </div>
        """

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Invitation to view StratAI report</title>
</head>
<body style="margin: 0; padding: 0; background-color: #FAF8F5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1A1A1A;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #FAF8F5; padding: 40px 16px;">
    <tr>
      <td align="center">
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 540px; background-color: #FFFFFF; border: 1px solid #E8E4DC; border-radius: 16px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.03); overflow: hidden;">
          
          <!-- Brand Header -->
          <tr>
            <td style="padding: 32px 36px 20px 36px; border-bottom: 1px solid #F3EFEA;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td>
                    <div style="display: inline-flex; align-items: center; gap: 8px;">
                      <span style="font-size: 20px; font-weight: 700; color: #1A1A1A; letter-spacing: -0.02em;">Strat<span style="color: #D4A843;">AI</span></span>
                    </div>
                  </td>
                  <td align="right">
                    <span style="font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: #B8912E; background: rgba(212, 168, 67, 0.1); padding: 4px 10px; border-radius: 9999px;">Shared Strategy</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Main Content -->
          <tr>
            <td style="padding: 32px 36px;">
              <h1 style="margin: 0 0 12px 0; font-size: 22px; font-weight: 700; color: #1A1A1A; line-height: 1.3;">
                You've been invited to view a strategy report
              </h1>
              <p style="margin: 0 0 20px 0; font-size: 15px; color: #6B6560; line-height: 1.55;">
                <strong style="color: #1A1A1A;">{inviter_name}</strong> ({inviter_email}) has invited you to view their shared AI strategy report:
              </p>

              <!-- Report Card -->
              <div style="background: #FDFCFB; border: 1px solid #E8E4DC; border-radius: 12px; padding: 18px 20px; margin-bottom: 24px;">
                <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: #B8912E; letter-spacing: 0.06em; margin-bottom: 4px;">
                  Strategy Chat Report
                </div>
                <div style="font-size: 17px; font-weight: 600; color: #1A1A1A;">
                  {chat_title}
                </div>
              </div>

              {custom_msg_section}

              <!-- CTA Button -->
              <table width="100%" cellpadding="0" cellspacing="0" style="margin: 28px 0;">
                <tr>
                  <td align="center">
                    <a href="{full_share_url}" target="_blank" style="display: inline-block; background: linear-gradient(135deg, #D4A843, #B8912E); color: #FFFFFF; text-decoration: none; font-size: 15px; font-weight: 600; padding: 13px 32px; border-radius: 10px; box-shadow: 0 4px 14px rgba(212, 168, 67, 0.25);">
                      Open Strategy Report →
                    </a>
                  </td>
                </tr>
              </table>

              <p style="margin: 0; font-size: 13px; color: #8C857B; line-height: 1.5; text-align: center;">
                🔒 This secure snapshot link is valid for <strong>3 days</strong>.
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding: 24px 36px; background-color: #FAF8F5; border-top: 1px solid #F0ECE4; text-align: center;">
              <p style="margin: 0 0 6px 0; font-size: 12px; color: #8C857B;">
                Sent via StratAI &bull; Automated Strategy Execution Engine
              </p>
              <p style="margin: 0; font-size: 11px; color: #A39E97;">
                If you were not expecting this invitation, you can safely ignore this email.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def send_chat_invitation_email(
    to_email: str,
    inviter_name: str,
    inviter_email: str,
    chat_title: str,
    share_url: str,
    custom_message: Optional[str] = None,
) -> bool:
    """
    Composes and delivers a shared chat invitation email.
    """
    full_url = share_url
    if not full_url.startswith("http"):
        _, _, _, _, _, _, default_app_url = _get_smtp_config()
        base = default_app_url.rstrip("/")
        path = share_url.lstrip("/")
        full_url = f"{base}/{path}"

    subject = f"{inviter_name} shared a strategy report with you: '{chat_title}'"
    html_body = build_invitation_html(
        inviter_name=inviter_name,
        inviter_email=inviter_email,
        chat_title=chat_title,
        full_share_url=full_url,
        custom_message=custom_message,
    )
    text_body = (
        f"Hi,\n\n"
        f"{inviter_name} ({inviter_email}) has invited you to view their strategy report '{chat_title}' on StratAI.\n\n"
        f"View the report here: {full_url}\n\n"
        f"Note: This link is valid for 3 days.\n\n"
        f"— StratAI Team"
    )

    return send_email(
        to_email=to_email,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
    )


def build_password_reset_html(
    user_name: Optional[str],
    reset_url: str,
) -> str:
    """Renders a refined, professional HTML password reset email for StratAI."""
    greeting = f"Hi {user_name}," if user_name and user_name.strip() else "Hello,"

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Reset Your StratAI Password</title>
</head>
<body style="margin: 0; padding: 0; background-color: #FAF8F5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1A1A1A;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #FAF8F5; padding: 40px 16px;">
    <tr>
      <td align="center">
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 520px; background-color: #FFFFFF; border: 1px solid #E8E4DC; border-radius: 16px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.03); overflow: hidden;">
          
          <!-- Brand Header -->
          <tr>
            <td style="padding: 32px 36px 20px 36px; border-bottom: 1px solid #F3EFEA;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td>
                    <span style="font-size: 20px; font-weight: 700; color: #1A1A1A; letter-spacing: -0.02em;">Strat<span style="color: #D4A843;">AI</span></span>
                  </td>
                  <td align="right">
                    <span style="font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: #B8912E; background: rgba(212, 168, 67, 0.1); padding: 4px 10px; border-radius: 9999px;">Security</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Main Content -->
          <tr>
            <td style="padding: 32px 36px;">
              <h1 style="margin: 0 0 14px 0; font-size: 22px; font-weight: 700; color: #1A1A1A; line-height: 1.3;">
                Reset Your Password
              </h1>
              <p style="margin: 0 0 16px 0; font-size: 15px; color: #4B453E; line-height: 1.55;">
                {greeting}
              </p>
              <p style="margin: 0 0 24px 0; font-size: 15px; color: #6B6560; line-height: 1.55;">
                We received a request to reset your password for your StratAI account. Click the button below to choose a new password:
              </p>

              <!-- CTA Button -->
              <table width="100%" cellpadding="0" cellspacing="0" style="margin: 28px 0;">
                <tr>
                  <td align="center">
                    <a href="{reset_url}" target="_blank" style="display: inline-block; background: #1A1A1A; color: #FFFFFF; text-decoration: none; font-size: 15px; font-weight: 600; padding: 13px 32px; border-radius: 10px; box-shadow: 0 4px 14px rgba(0, 0, 0, 0.15);">
                      Reset Password →
                    </a>
                  </td>
                </tr>
              </table>

              <!-- Fallback Link -->
              <p style="margin: 24px 0 8px 0; font-size: 13px; color: #8C857B; line-height: 1.5;">
                If the button above does not work, copy and paste this link into your browser:
              </p>
              <p style="margin: 0 0 24px 0; font-size: 12px; color: #B8912E; word-break: break-all; line-height: 1.5;">
                <a href="{reset_url}" style="color: #B8912E; text-decoration: underline;">{reset_url}</a>
              </p>

              <div style="background: #FAF8F5; border-radius: 8px; padding: 12px 16px; margin-top: 16px;">
                <p style="margin: 0; font-size: 12px; color: #8C857B; line-height: 1.5;">
                  ⏳ <strong>This link expires in 1 hour</strong> for your security.<br/>
                  If you did not request a password reset, you can safely ignore this email — your account remains secure.
                </p>
              </div>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding: 24px 36px; background-color: #FAF8F5; border-top: 1px solid #F0ECE4; text-align: center;">
              <p style="margin: 0 0 6px 0; font-size: 12px; color: #8C857B;">
                Sent via StratAI &bull; Automated Strategy Execution Engine
              </p>
              <p style="margin: 0; font-size: 11px; color: #A39E97;">
                ai@vichitraa.agency
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def send_password_reset_email(
    to_email: str,
    reset_token: str,
    user_name: Optional[str] = None,
    frontend_url: Optional[str] = None,
) -> bool:
    """
    Composes and delivers a password reset email with the reset token link.
    """
    if not frontend_url:
        _, _, _, _, _, _, default_app_url = _get_smtp_config()
        base_url = default_app_url.rstrip("/")
    else:
        base_url = frontend_url.rstrip("/")
    reset_url = f"{base_url}/reset-password?token={reset_token}"

    subject = "Reset your StratAI password"
    html_body = build_password_reset_html(user_name=user_name, reset_url=reset_url)
    text_body = (
        f"Hi{' ' + user_name if user_name else ''},\n\n"
        f"We received a request to reset your password for your StratAI account.\n\n"
        f"Click the link below to set a new password:\n{reset_url}\n\n"
        f"Note: This link will expire in 1 hour.\n\n"
        f"If you did not request this, please ignore this email.\n\n"
        f"— StratAI Team"
    )

    return send_email(
        to_email=to_email,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
    )


def build_team_invitation_html(
    team_name: str,
    inviter_display: str,
    invite_url: str,
    to_email: str,
) -> str:
    """Renders a sleek, modern, executive HTML email invitation for StratAI."""
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Invitation to join {team_name} on StratAI</title>
</head>
<body style="margin: 0; padding: 0; background-color: #FAF8F5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1A1A1A; -webkit-font-smoothing: antialiased;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #FAF8F5; padding: 48px 16px;">
    <tr>
      <td align="center">
        <!-- Main Card Container -->
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 560px; background-color: #FFFFFF; border: 1px solid #E8E4DC; border-radius: 18px; box-shadow: 0 8px 30px rgba(0, 0, 0, 0.04); overflow: hidden;">
          
          <!-- Brand Header -->
          <tr>
            <td style="padding: 32px 40px 24px 40px; border-bottom: 1px solid #F3EFEA; background: #FFFFFF;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td>
                    <div style="display: inline-flex; align-items: center; gap: 8px;">
                      <span style="font-size: 22px; font-weight: 700; color: #1A1A1A; letter-spacing: -0.03em;">
                        Strat<span style="color: #D4A843;">AI</span>
                      </span>
                    </div>
                  </td>
                  <td align="right">
                    <span style="display: inline-block; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #1A1A1A; background: #FAF8F5; border: 1px solid #E8E4DC; padding: 5px 12px; border-radius: 9999px;">
                      Team Invitation
                    </span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Main Content -->
          <tr>
            <td style="padding: 40px 40px 32px 40px;">
              <h1 style="margin: 0 0 14px 0; font-size: 26px; font-weight: 700; color: #1A1A1A; line-height: 1.25; letter-spacing: -0.02em;">
                Join {team_name}
              </h1>
              
              <p style="margin: 0 0 24px 0; font-size: 15px; color: #55504B; line-height: 1.6;">
                <strong style="color: #1A1A1A;">{inviter_display}</strong> has invited you to collaborate in their shared strategy workspace on StratAI.
              </p>

              <!-- Workspace Card Summary -->
              <div style="background: #FDFBF7; border: 1px solid #EAE4D6; border-left: 4px solid #D4A843; border-radius: 12px; padding: 20px 22px; margin-bottom: 28px;">
                <div style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: #B8912E; letter-spacing: 0.06em; margin-bottom: 6px;">
                  Shared Workspace
                </div>
                <div style="font-size: 18px; font-weight: 700; color: #1A1A1A; margin-bottom: 4px;">
                  {team_name}
                </div>
                <div style="font-size: 13px; color: #6B6560; line-height: 1.4;">
                  Collaborate on AI-powered market positioning, strategic competitor audits, and shared project execution.
                </div>
              </div>

              <!-- Feature Highlights -->
              <div style="background: #FAF8F5; border-radius: 12px; padding: 16px 20px; margin-bottom: 32px;">
                <div style="font-size: 12px; font-weight: 700; color: #1A1A1A; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 0.04em;">
                  What you get access to:
                </div>
                <table width="100%" cellpadding="0" cellspacing="0" style="font-size: 13.5px; color: #4A4540; line-height: 1.6;">
                  <tr>
                    <td style="padding-bottom: 8px; vertical-align: top; width: 20px; color: #D4A843;">✦</td>
                    <td style="padding-bottom: 8px;"><strong>Shared Strategy Intelligence</strong> — View real-time strategy decks & competitive scans</td>
                  </tr>
                  <tr>
                    <td style="padding-bottom: 8px; vertical-align: top; width: 20px; color: #D4A843;">✦</td>
                    <td style="padding-bottom: 8px;"><strong>Team Workspace</strong> — Collaborative project sharing and live report access</td>
                  </tr>
                  <tr>
                    <td style="vertical-align: top; width: 20px; color: #D4A843;">✦</td>
                    <td><strong>Centralized Organization</strong> — Direct integration across tools & connectors</td>
                  </tr>
                </table>
              </div>

              <!-- Primary CTA Button -->
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 28px;">
                <tr>
                  <td align="center">
                    <a href="{invite_url}" target="_blank" style="display: inline-block; background-color: #000000; color: #FFFFFF; font-size: 15px; font-weight: 600; text-decoration: none; padding: 15px 36px; border-radius: 10px; box-shadow: 0 4px 14px rgba(0, 0, 0, 0.15); transition: background-color 0.2s;">
                      Accept Invitation &amp; Join Team &rarr;
                    </a>
                  </td>
                </tr>
              </table>

              <!-- Link Fallback -->
              <div style="background: #FFFFFF; border: 1px solid #E8E4DC; border-radius: 8px; padding: 12px 14px; margin-bottom: 24px; font-size: 12px; color: #8C857B; word-break: break-all; line-height: 1.4;">
                <strong style="color: #4A4540;">Direct link:</strong><br/>
                <a href="{invite_url}" style="color: #B8912E; text-decoration: underline;">{invite_url}</a>
              </div>

              <!-- Security Callout -->
              <p style="margin: 0; font-size: 12.5px; color: #8C857B; line-height: 1.5; text-align: center;">
                🔒 This invitation is valid for <strong>7 days</strong> and addressed to <strong>{to_email}</strong>.<br/>
                If you already have an account, you will simply sign in to accept.
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding: 24px 40px; background-color: #FAF8F5; border-top: 1px solid #F0ECE4; text-align: center;">
              <p style="margin: 0 0 6px 0; font-size: 12px; font-weight: 500; color: #7A746E;">
                Sent via StratAI &bull; AI Strategy &amp; Execution Engine
              </p>
              <p style="margin: 0; font-size: 11px; color: #A39E97;">
                If you were not expecting this invitation, you can safely ignore this email.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def send_team_invitation_email(
    to_email: str,
    invite_token: str,
    team_name: str,
    inviter_name: Optional[str] = None,
    frontend_url: Optional[str] = None,
) -> bool:
    """Composes and delivers an email inviting a member to join a StratAI team workspace."""
    if not frontend_url:
        _, _, _, _, _, _, default_app_url = _get_smtp_config()
        base_url = default_app_url.rstrip("/")
    else:
        base_url = frontend_url.rstrip("/")
    invite_url = f"{base_url}/auth?invite_token={invite_token}&email={to_email}"

    inviter_display = inviter_name or "A team administrator"
    subject = f"You've been invited to join {team_name} on StratAI"
    html_body = build_team_invitation_html(
        team_name=team_name,
        inviter_display=inviter_display,
        invite_url=invite_url,
        to_email=to_email,
    )

    text_body = (
        f"Hi,\n\n"
        f"{inviter_display} has invited you to join '{team_name}' on StratAI.\n\n"
        f"Accept the invitation by clicking the link below:\n{invite_url}\n\n"
        f"Note: This invitation is valid for 7 days.\n\n"
        f"— StratAI Team"
    )

    return send_email(
        to_email=to_email,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
    )
