"""Job tracking: canonical jobs, per-board postings, and applications.

CanonicalJob groups postings that are the same role (matched by signature) so the same
job seen on multiple boards is recognised. See dev/25_06_minimal_req.md (Data model).
"""
from django.db import models


class CanonicalJob(models.Model):
    """One real-world role; postings across boards collapse into this via `signature`."""

    signature = models.CharField(max_length=64, unique=True, db_index=True)
    company = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    location = models.CharField(max_length=255, blank=True)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} @ {self.company}"


class JobPosting(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"
        UNKNOWN = "unknown", "Unknown"

    canonical_job = models.ForeignKey(CanonicalJob, on_delete=models.CASCADE, related_name="postings")
    url = models.URLField(max_length=1000, unique=True)
    source_board = models.CharField(max_length=100, blank=True)
    raw_html = models.TextField(blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.UNKNOWN)
    scraped_at = models.DateTimeField(null=True, blank=True)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.url


class Application(models.Model):
    class Status(models.TextChoices):
        APPLIED = "applied", "Applied"
        INTERVIEW = "interview", "Interview"
        OFFER = "offer", "Offer"
        REJECTED = "rejected", "Rejected"

    posting = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name="applications")
    tailored_resume = models.ForeignKey(
        "tailoring.TailoredResume", on_delete=models.SET_NULL, null=True, blank=True
    )
    applied_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.APPLIED)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.posting} ({self.status})"
