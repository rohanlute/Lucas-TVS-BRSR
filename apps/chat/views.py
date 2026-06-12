from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from apps.accounts.models import User
from django.shortcuts import redirect
from django.views import View
from .models import (Conversation,ConversationParticipant,Message)
from django.shortcuts import get_object_or_404
from apps.accounts.models import User
from django.http import JsonResponse
from django.views import View
from django.db.models import OuterRef, Subquery
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone

class ChatView(LoginRequiredMixin, TemplateView):

    login_url = 'accounts:login'
    template_name = 'applications/chat.html'

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        context['page_title'] = 'Chat'

        # Super Admin
        if self.request.user.is_superuser:

            users = User.objects.exclude(
                id=self.request.user.id
            ).order_by('first_name')

        # Normal User
        else:

            conversations = Conversation.objects.filter(
                participants__user=self.request.user
            ).distinct()

            user_ids = []

            for conversation in conversations:

                participants = conversation.participants.exclude(
                    user=self.request.user
                )

                for participant in participants:

                    user_ids.append(
                        participant.user.id
                    )

            users = User.objects.filter(
                id__in=user_ids
            ).order_by('first_name')

        # Last Message + Unread Count
        for user in users:

            conversation_obj = None

            conversations = Conversation.objects.filter(
                participants__user=self.request.user
            )

            for conv in conversations:

                participant_ids = list(
                    conv.participants.values_list(
                        'user_id',
                        flat=True
                    )
                )

                if set(participant_ids) == {
                    self.request.user.id,
                    user.id
                }:
                    conversation_obj = conv
                    break

            if conversation_obj:

                last_message = Message.objects.filter(
                    conversation=conversation_obj
                ).order_by('-created_at').first()

                user.last_message = (
                    last_message.message
                    if last_message else ''
                )

                user.unread_count = Message.objects.filter(
                    conversation=conversation_obj,
                    is_read=False
                ).exclude(
                    sender=self.request.user
                ).count()

            else:

                user.last_message = ''
                user.unread_count = 0

        context['users'] = users

        return context
        
    



class StartChatView(LoginRequiredMixin, View):

    login_url = 'accounts:login'

    def get(self, request, user_id):

        other_user = User.objects.get(id=user_id)

        current_user = request.user

        conversations = Conversation.objects.filter(participants__user=current_user)

        conversation = None

        for conv in conversations:

            participant_ids = list(conv.participants.values_list('user_id',flat=True))

            if set(participant_ids) == {
                current_user.id,
                other_user.id
            }:
                conversation = conv
                break

        if not conversation:

            conversation = Conversation.objects.create()

            ConversationParticipant.objects.create(conversation=conversation,user=current_user)

            ConversationParticipant.objects.create(conversation=conversation,user=other_user)

        return redirect('chat:conversation',conversation_id=conversation.id)
    




class ConversationView(LoginRequiredMixin, TemplateView):

    login_url = 'accounts:login'
    template_name = 'applications/chat.html'

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        conversation = get_object_or_404(
            Conversation,
            id=self.kwargs['conversation_id']
        )


        unread_messages = Message.objects.filter(conversation=conversation,is_read=False).exclude(sender=self.request.user)

        channel_layer = get_channel_layer()

        for msg in unread_messages:

            msg.is_read = True
            msg.save(update_fields=['is_read'])

            async_to_sync(channel_layer.group_send)(
                f'chat_{conversation.id}',
                {
                    'type': 'read_message',
                    'message_id': msg.id
                }
            )

        context['conversation'] = conversation

        context['messages'] = Message.objects.filter(conversation=conversation).select_related('sender')

        users = User.objects.exclude(id=self.request.user.id)

        for user in users:

            conversation_obj = None

            conversations = Conversation.objects.filter(participants__user=self.request.user)

            for conv in conversations:

                participant_ids = list(conv.participants.values_list('user_id',flat=True))

                if set(participant_ids) == {
                    self.request.user.id,
                    user.id
                }:
                    conversation_obj = conv
                    break

            if conversation_obj:

                last_message = Message.objects.filter(conversation=conversation_obj).order_by('-created_at').first()

                user.last_message = (last_message.message if last_message else '')

                user.unread_count = Message.objects.filter(conversation=conversation_obj,is_read=False).exclude(sender=self.request.user).count()

            else:

                user.last_message = ''

                user.unread_count = 0

        context['users'] = users

        active_user_id = None

        active_user = None

        for participant in conversation.participants.all():

            if participant.user != self.request.user:

                active_user = participant.user

        context['active_user'] = active_user

        for participant in conversation.participants.all():

            if participant.user != self.request.user:

                active_user_id = participant.user.id

        context['active_user_id'] = active_user_id

        return context

    def post(self, request, *args, **kwargs):

        conversation = get_object_or_404(
            Conversation,
            id=self.kwargs['conversation_id']
        )

        message = request.POST.get('message')

        if message:

            Message.objects.create(
                conversation=conversation,
                sender=request.user,
                message=message
            )

        return redirect(
            'chat:conversation',
            conversation_id=conversation.id
        )
    




class SendMessageView(LoginRequiredMixin, View):

    def post(self, request):

        conversation_id = request.POST.get(
            'conversation_id'
        )

        message_text = request.POST.get(
            'message'
        )

        conversation = Conversation.objects.get(
            id=conversation_id
        )

        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            message=message_text,
            delivered=True
        )

        return JsonResponse({
            'success': True,
            'message': message.message,
            'sender': str(request.user),
            'time': timezone.localtime(message.created_at).strftime('%H:%M'),
            'delivered': message.delivered,
            'is_read': message.is_read,
            'message_id': message.id
        })
    


class MessageListView(LoginRequiredMixin, View):

    def get(self, request, conversation_id):

        messages = Message.objects.filter(conversation_id=conversation_id).select_related('sender')

        data = []

        for msg in messages:

            data.append({
                'id': msg.id,
                'message': msg.message,
                'sender': str(msg.sender),
                'time': msg.created_at.strftime('%H:%M'),
                'is_me': msg.sender_id == request.user.id,
                'is_read': msg.is_read
            })

        return JsonResponse({'messages': data})