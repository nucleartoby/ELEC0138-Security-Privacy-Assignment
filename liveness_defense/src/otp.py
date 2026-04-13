"""
OTP (One-Time Password) Service Module

This module provides functionality for generating, sending, and verifying
time-limited OTP codes via email for authentication purposes.
"""

import time
import random
import hashlib
import smtplib
import ssl
import os
import certifi
from email.message import EmailMessage
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class OTPService:
    """
    Service for handling OTP generation, email delivery, and verification.

    This class manages the complete OTP lifecycle including generation of
    secure random codes, sending them via Gmail SMTP, and verifying user input
    with attempt limits and expiration handling.
    """

    def __init__(self):
        """Initialize the OTP service with email configuration."""
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 465

        # Load email credentials from environment variables
        self.sender_email = os.getenv("SENDER_EMAIL")
        self.sender_password = os.getenv("SENDER_PASSWORD")
        self.recipient_email = os.getenv("RECEIVER_EMAIL")

        # OTP state management
        self.otp_hash = None  # Hashed OTP for security
        self.expiry_time = None  # When OTP expires
        self.max_attempts = 3  # Maximum verification attempts
        self.attempts = 0  # Current attempt count
        self.validity_seconds = 120  # OTP validity period in seconds

    def _hash_otp(self, otp):
        """
        Hash the OTP for secure storage and comparison.

        Args:
            otp (str): The OTP string to hash

        Returns:
            str: SHA-256 hash of the OTP
        """
        return hashlib.sha256(otp.encode()).hexdigest()

    def generate_otp(self):
        """
        Generate a random 6-digit OTP.

        Returns:
            str: 6-digit numeric OTP as string
        """
        return str(random.randint(100000, 999999))

    def send_otp(self):
        """
        Generate and send OTP via email.

        Creates a new OTP, hashes it for storage, sets expiry time,
        and sends it to the configured recipient email.

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        if not self.sender_email or not self.sender_password or not self.recipient_email:
            print("Missing email environment variables.")
            return False

        otp = self.generate_otp()
        self.otp_hash = self._hash_otp(otp)
        self.expiry_time = time.time() + self.validity_seconds
        self.attempts = 0

        subject = "Your Verification Code"
        body = f"Your verification code is: {otp}\nIt expires in {self.validity_seconds} seconds."

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.sender_email
        msg["To"] = self.recipient_email
        msg.set_content(body)

        msg.set_content(body)

        try:
            # Create SSL context for secure connection
            context = ssl.create_default_context(cafile=certifi.where())

            if self.smtp_port == 465:
                # Use SSL connection
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=context) as server:
                    server.login(self.sender_email, self.sender_password)
                    server.send_message(msg)
            else:
                # Use STARTTLS upgrade
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.starttls(context=context)
                    server.login(self.sender_email, self.sender_password)
                    server.send_message(msg)

            print("OTP sent via email.")
            return True

        except Exception as e:
            print("Failed to send OTP:", e)
            return False

    def verify_otp(self, user_input):
        """
        Verify user-provided OTP against stored hash.

        Checks for OTP existence, expiration, attempt limits, and correctness.
        Resets state on successful verification.

        Args:
            user_input (str): The OTP entered by the user

        Returns:
            bool: True if OTP is valid, False otherwise
        """
        if self.otp_hash is None:
            print("No OTP generated.")
            return False

        if time.time() > self.expiry_time:
            print("OTP expired.")
            return False

        if self.attempts >= self.max_attempts:
            print("Too many attempts.")
            return False

        self.attempts += 1

        if self._hash_otp(user_input) == self.otp_hash:
            print("OTP verified successfully.")
            self.reset()
            return True

        print(f"Incorrect OTP. Attempts left: {self.max_attempts - self.attempts}")
        return False

    def reset(self):
        """
        Reset OTP state to allow new OTP generation.

        Clears the stored hash, expiry time, and attempt counter.
        """
        self.otp_hash = None
        self.expiry_time = None
        self.attempts = 0