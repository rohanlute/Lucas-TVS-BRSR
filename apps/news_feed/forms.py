from pathlib import Path
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import transaction
from .models import *


DATETIME_LOCAL_FORMAT = "%Y-%m-%dT%H:%M"


class BootstrapFormMixin:
    """Apply common Bootstrap-friendly classes to form widgets."""

    def apply_widget_classes(self):
        for field in self.fields.values():
            widget = field.widget
            existing = widget.attrs.get("class", "")
            if isinstance(widget, forms.CheckboxInput):
                css_class = "form-check-input"
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                css_class = "form-select"
            else:
                css_class = "form-control"
            widget.attrs["class"] = f"{existing} {css_class}".strip()


# Main News / Event form
class NewsEventForm(BootstrapFormMixin, forms.ModelForm):
    """Create or edit a News item or Event.

    `is_event=False` means News; `is_event=True` means Event.
    For News, start_datetime is the publication/scheduled publication time.
    For Events, start_datetime and end_datetime are the event time range.
    """

    is_event = forms.TypedChoiceField(
        label="Content type",
        choices=(("False", "News"), ("True", "Event")),
        coerce=lambda value: str(value).lower() in {"true", "1"},
        initial="False",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    reminder_days = forms.MultipleChoiceField(
        label="Remind users before the event",
        choices=REMINDER_DAY_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    reminder_send_time = forms.ChoiceField(
        label="Send reminders at",
        choices=(("08:00", "08:00 AM"), ("09:00", "09:00 AM"), ("10:00", "10:00 AM")),
        required=False,
        initial="09:00",
        widget=forms.RadioSelect,
    )

    class Meta:
        model = NewsEvent
        fields = [
            "is_event",
            "title",
            "description",
            "start_datetime",
            "end_datetime",
            "meeting_link",
            "all_plants",
            "plants",
            "departments",
            "reminder_days",
            "reminder_send_time",
            "status",
        ]
        widgets = {
            "is_event": forms.Select(
                choices=(("False", "News"), ("True", "Event")),
                attrs={"class": "form-select"},
            ),
            "title": forms.TextInput(
                attrs={"placeholder": "Enter news or event title", "maxlength": 255}
            ),
            "description": forms.Textarea(
                attrs={"rows": 6, "placeholder": "Enter the details users should know..."}
            ),
            "start_datetime": forms.DateTimeInput(
                format=DATETIME_LOCAL_FORMAT,
                attrs={"type": "datetime-local"},
            ),
            "end_datetime": forms.DateTimeInput(
                format=DATETIME_LOCAL_FORMAT,
                attrs={"type": "datetime-local"},
            ),
            "meeting_link": forms.URLInput(
                attrs={"placeholder": "https://example.com/meeting"}
            ),
            "all_plants": forms.CheckboxInput(),
            "plants": forms.SelectMultiple(attrs={"size": 6}),
            "departments": forms.SelectMultiple(attrs={"size": 6}),
            "status": forms.HiddenInput(),
        }
        labels = {
            "is_event": "Content type",
            "start_datetime": "Start date and time",
            "end_datetime": "End date and time",
            "meeting_link": "Meeting link",
            "all_plants": "All plants",
            "plants": "Select plants",
            "departments": "Select departments",
        }
        help_texts = {
            "start_datetime": (
                "For News, this is the publication date/time. "
                "For Events, this is the event start date/time."
            ),
            "end_datetime": (
                "For Events, this is the event end date/time. "
                "For News, it can be used as an optional expiry date/time."
            ),
            "all_plants": "Select this to make the item available to all plants.",
            "plants": "Select one or more plants when All plants is not selected.",
            "departments": "Optionally restrict visibility to selected departments.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # The supplied Plant and Department models both have is_active fields.
        if "plants" in self.fields:
            self.fields["plants"].queryset = self.fields["plants"].queryset.filter(
                is_active=True
            )
        if "departments" in self.fields:
            self.fields["departments"].queryset = self.fields[
                "departments"
            ].queryset.filter(is_active=True)

        # datetime-local expects YYYY-MM-DDTHH:MM.
        for name in ("start_datetime", "end_datetime"):
            self.fields[name].input_formats = [
                DATETIME_LOCAL_FORMAT,
                "%Y-%m-%dT%H:%M:%S",
            ]

        self.apply_widget_classes()

        # Existing reminder rules populate the chips when editing an event.
        if self.instance and self.instance.pk and not self.is_bound:
            rules = list(self.instance.reminder_rules.filter(is_active=True))
            self.initial["reminder_days"] = [str(rule.days_before) for rule in rules]
            if rules:
                self.initial["reminder_send_time"] = rules[0].send_time.strftime("%H:%M")

        # Keep the type selector visually consistent with the segmented UI.
        self.fields["is_event"].widget.attrs["class"] = "form-select"

    def clean(self):
        cleaned_data = super().clean()

        is_event = cleaned_data.get("is_event")
        start_datetime = cleaned_data.get("start_datetime")
        end_datetime = cleaned_data.get("end_datetime")
        all_plants = cleaned_data.get("all_plants")
        plants = cleaned_data.get("plants")

        if end_datetime and start_datetime and end_datetime <= start_datetime:
            self.add_error(
                "end_datetime",
                "End date/time must be later than the start date/time.",
            )

        if is_event and not start_datetime:
            self.add_error(
                "start_datetime",
                "An event start date and time is required.",
            )

        if (
            cleaned_data.get("status") == NewsEvent.Status.SCHEDULED
            and not start_datetime
        ):
            self.add_error(
                "start_datetime",
                "A date and time is required before scheduling this item.",
            )

        if not all_plants and not plants:
            self.add_error(
                "plants",
                "Select at least one plant or enable All plants.",
            )

        # Avoid persisting a partial plant selection when All plants is enabled.
        if all_plants and "plants" in cleaned_data:
            cleaned_data["plants"] = self.fields["plants"].queryset.none()

        return cleaned_data


# Multiple attachment upload
class MultipleFileInput(forms.ClearableFileInput):
    """A file input that accepts multiple files in one selection."""

    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """Validate each uploaded file while returning a list of files."""

    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if not data:
            return []

        files = data if isinstance(data, (list, tuple)) else [data]
        cleaned_files = []
        for uploaded_file in files:
            if uploaded_file is None:
                continue
            cleaned_files.append(super().clean(uploaded_file, initial))
        return cleaned_files


class NewsEventAttachmentUploadForm(BootstrapFormMixin, forms.Form):
    """Upload multiple documents/images for one NewsEvent.

    File type is detected from the extension:
      - PDF, DOCX, XLSX -> Document
      - JPG, JPEG, PNG -> Image

    Call `save_attachments(content, uploaded_by=request.user)` after the
    parent NewsEvent has been saved.
    """

    files = MultipleFileField(
        required=False,
        validators=[
            FileExtensionValidator(
                allowed_extensions=ALLOWED_ATTACHMENT_EXTENSIONS
            ),
            validate_news_event_attachment_size,
        ],
        widget=MultipleFileInput(
            attrs={
                "accept": ".pdf,.docx,.xlsx,.jpg,.jpeg,.png",
                "multiple": True,
            }
        ),
        help_text="PDF, DOCX, XLSX, JPG or PNG. Maximum 10 MB per file.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["files"].widget.attrs["class"] = "form-control"

    def clean_files(self):
        uploaded_files = self.cleaned_data.get("files", [])
        for uploaded_file in uploaded_files:
            if uploaded_file.size > MAX_ATTACHMENT_SIZE:
                raise ValidationError(
                    f"{uploaded_file.name}: each attachment must be 10 MB or smaller."
                )
        return uploaded_files

    @transaction.atomic
    def save_attachments(self, content, uploaded_by=None):
        """Create and return attachment records for all selected files."""
        if not content or not content.pk:
            raise ValueError(
                "Save the NewsEvent first, then save its attachments."
            )

        created_attachments = []
        image_extensions = {"jpg", "jpeg", "png"}

        for uploaded_file in self.cleaned_data.get("files", []):
            extension = Path(uploaded_file.name).suffix.lower().lstrip(".")
            attachment_type = (
                NewsEventAttachment.AttachmentType.IMAGE
                if extension in image_extensions
                else NewsEventAttachment.AttachmentType.DOCUMENT
            )

            attachment = NewsEventAttachment(
                content=content,
                file=uploaded_file,
                attachment_type=attachment_type,
                original_name=Path(uploaded_file.name).name,
                uploaded_by=uploaded_by,
            )
            attachment.full_clean()
            attachment.save()
            created_attachments.append(attachment)

        return created_attachments


class NewsEventAttachmentForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = NewsEventAttachment
        fields = ["file", "attachment_type", "caption"]
        widgets = {
            "file": forms.ClearableFileInput(
                attrs={"accept": ".pdf,.docx,.xlsx,.jpg,.jpeg,.png"}
            ),
            "attachment_type": forms.Select(),
            "caption": forms.TextInput(
                attrs={"placeholder": "Optional attachment caption"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_widget_classes()


