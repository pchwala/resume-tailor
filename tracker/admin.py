from django.contrib import admin

from .models import Application, CanonicalJob, JobPosting


@admin.register(CanonicalJob)
class CanonicalJobAdmin(admin.ModelAdmin):
    list_display = ("title", "company", "location", "last_seen")
    search_fields = ("title", "company", "signature")


@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
    list_display = ("url", "source_board", "status", "scraped_at")
    list_filter = ("status", "source_board")


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("posting", "status", "applied_at")
    list_filter = ("status",)
