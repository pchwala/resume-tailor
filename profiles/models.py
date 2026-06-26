"""Master resume data — the fixed source the AI tailors from.

Mirrors the sections of printable_resume/index.html. Fields marked "fixed" are rendered
verbatim and must never be altered by tailoring (see tailoring/ai.py's subset guard);
free-form prose fields are the AI's starting point.
"""
from django.db import models


class Profile(models.Model):
    """Singleton-ish identity + header/footer data. All fields fixed (never tailored)."""

    name = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True, help_text="Headline, e.g. 'Software Developer & Problem Solver'")
    location = models.CharField(max_length=255, blank=True)
    website_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    email = models.EmailField(blank=True)
    linkedin_url = models.URLField(blank=True)
    about = models.TextField(blank=True, help_text="Master summary; tailoring rewrites a copy of this.")
    gdpr_text = models.TextField(blank=True, help_text="Recruitment-consent footer.")

    def __str__(self):
        return self.name


class SkillCategory(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="skill_categories")
    name = models.CharField(max_length=100, help_text="e.g. 'Frameworks'")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name_plural = "skill categories"

    def __str__(self):
        return self.name


class Skill(models.Model):
    category = models.ForeignKey(SkillCategory, on_delete=models.CASCADE, related_name="skills")
    name = models.CharField(max_length=100, help_text="The chip text, e.g. 'FastAPI'")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


class Experience(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="experiences")
    company = models.CharField(max_length=255, help_text="Fixed fact.")
    period = models.CharField(max_length=100, help_text="Fixed fact, e.g. '2022 — Present'")
    description = models.TextField(help_text="Master prose; tailorable.")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.company


class Project(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="projects")
    name = models.CharField(max_length=255, help_text="Fixed fact.")
    tech = models.JSONField(default=list, blank=True, help_text="Fixed list of tech-chip strings.")
    description = models.TextField(help_text="Master prose; tailorable.")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.name
