from .constants import *

from .handlers.notification_handler import NotificationHandler
from .handlers.timesheet_handler import TimesheetHandler


HANDLER_REGISTRY = {

    NOTIFICATION: NotificationHandler,

    TIMESHEET: TimesheetHandler,

}