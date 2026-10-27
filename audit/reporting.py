import pandas as pd
from fpdf import FPDF
import pyttsx3
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

class AuditReport:
    def __init__(self, data):
        self.data = data

    def generate_pdf(self, filename):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt="Audit Report", ln=True, align='C')
        pdf.cell(200, 10, txt="Date: " + pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'), ln=True, align='C')
        pdf.cell(200, 10, txt="", ln=True)
        pdf.set_font("Arial", size=10)
        pdf.write_html(self.data.to_html(index=False))
        pdf.output(filename)
        print(f"PDF report generated: {filename}")

    def generate_spoken_report(self):
        engine = pyttsx3.init()
        engine.say(self.data.to_string(index=False))
        engine.runAndWait()
        print("Spoken report generated.")

    def generate_email_report(self, recipient_email, subject, sender_email, sender_password):
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        body = f"Audit Report for {pd.Timestamp.now().strftime('%Y-%m-%d')}\n\n"
        body += self.data.to_string(index=False)
        msg.attach(MIMEText(body, 'plain'))
        
        pdf_filename = "audit_report.pdf"
        self.generate_pdf(pdf_filename)
        
        with open(pdf_filename, "rb") as attachment:
            part = MIMEApplication(attachment.read(), Name="audit_report.pdf")
            part['Content-Disposition'] = f'attachment; filename="audit_report.pdf"'
            msg.attach(part)
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, recipient_email, text)
        server.quit()
        print(f"Email report sent to: {recipient_email}")

# Example usage:
data = pd.DataFrame({
    'User': ['Alice', 'Bob', 'Charlie'],
    'Action': ['Login', 'Logout', 'Login'],
    'Timestamp': pd.to_datetime(['2023-04-01 10:00:00', '2023-04-01 10:05:00', '2023-04-01 10:10:00'])
})

audit_report = AuditReport(data)
if __name__ == "__main__":
    # Only run when executed directly, not on import
    audit_report.generate_pdf_report("audit_report.pdf")
    audit_report.generate_spoken_report()
    # Uncomment and fill in real credentials to send email:
    # audit_report.generate_email_report("recipient@example.com", "Audit Report", "sender@example.com", "password")