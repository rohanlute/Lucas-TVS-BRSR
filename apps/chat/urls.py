from django.urls import path
from .views import ChatView,StartChatView,ConversationView,SendMessageView,MessageListView

app_name = 'chat'

urlpatterns = [

    path('chat/',ChatView.as_view(),name='chat'),
    path('chat/user/<int:user_id>/',StartChatView.as_view(),name='start_chat'),
    path('conversation/<int:conversation_id>/',ConversationView.as_view(),name='conversation'),
    path('send-message/',SendMessageView.as_view(),name='send_message'),
    path('messages/<int:conversation_id>/',MessageListView.as_view(),name='message_list'),

]