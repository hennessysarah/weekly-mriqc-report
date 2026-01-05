# commands to send emails for MRIQC weekly script

# Sarah Hennessy, shennessy@arizona.edu
# last edit Jan 4, 2026



from __future__ import annotations
import subprocess
import shutil
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage

def _get_sendmail() -> str:
    sendmail_path = shutil.which("sendmail")
    if sendmail_path is None:
        raise RuntimeError("sendmail not installed on this system.")
    return sendmail_path

def send_email_plaintext(subject: str, recipient_list: list[str], body: str, sender: str) -> None:
    sendmail_path = _get_sendmail()
    message = (
        f"Subject: {subject}\n"
        f"From: {sender}\n"
        f"To: {', '.join(recipient_list)}\n\n"
        f"{body}"
    )
    p = subprocess.Popen([sendmail_path, "-t", "-oi"], stdin=subprocess.PIPE)
    p.communicate(message.encode("utf-8"))

def send_email_inline_images(
    *,
    subject: str,
    recipient_list: list[str],
    html_body: str,
    cid_to_path: dict[str, Path],
    sender: str,
) -> None:
    sendmail_path = _get_sendmail()

    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipient_list)

    msg.attach(MIMEText(html_body, "html"))

    for cid, img_path in cid_to_path.items():
        img_path = Path(img_path)
        with open(img_path, "rb") as f:
            img = MIMEImage(f.read())
        img.add_header("Content-ID", f"<{cid}>")
        img.add_header("Content-Disposition", "inline", filename=img_path.name)
        msg.attach(img)

    p = subprocess.Popen([sendmail_path, "-t", "-oi"], stdin=subprocess.PIPE)
    p.communicate(msg.as_bytes())
