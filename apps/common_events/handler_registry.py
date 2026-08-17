from .constants import *

from .handlers.notification_handler import NotificationHandler
from .handlers.timesheet_handler import TimesheetHandler
from .handlers.email_handler import EmailHandler

HANDLER_REGISTRY = {

    NOTIFICATION: NotificationHandler,

    TIMESHEET: TimesheetHandler,

    EMAIL: EmailHandler,

}