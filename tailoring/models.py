"""Resume templates and tailored outputs.

The tailored *structure* is driven by the JSON schema in tailoring/ai.py + the master data
in profiles/, not by a Markdown body — so ResumeTemplate only names a layout. TailoredResume
stores the validated tailored JSON. See dev/25_06_minimal_req.md (Data model).
"""
from django.db import models


class ResumeTemplate(models.Model):
    name = models.CharField(max_length=100)
    pdf_template_name = models.CharField(
        max_length=200,
        default="tracker/pdf_template.html",
        help_text="Django template used to render the PDF.",
    )
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class TailoredResume(models.Model):
    posting = models.ForeignKey(
        "tracker.JobPosting", on_delete=models.CASCADE, related_name="tailored_resumes"
    )
    template = models.ForeignKey(ResumeTemplate, on_delete=models.PROTECT, null=True, blank=True)
    content = models.JSONField(default=dict, help_text="Validated tailored-resume JSON.")
    model_used = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Tailored for {self.posting}"
