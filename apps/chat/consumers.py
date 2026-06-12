import json

from channels.generic.websocket import AsyncWebsocketConsumer


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        print("WEBSOCKET CONNECT HIT")

        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']

        self.room_group_name = (f'chat_{self.conversation_id}')

        await self.channel_layer.group_add(self.room_group_name,self.channel_name)

        await self.accept()


    async def disconnect(self,close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        event_type = data.get('type')
        if event_type == 'typing':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'typing_message',
                    'sender': data['sender']
                }
            )
        elif event_type == 'chat':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': data['message'],
                    'sender': data['sender'],
                    'time': data['time'],
                    'message_id': data['message_id']
                }
            )
        elif event_type == 'read':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'read_message',
                    'message_id': data['message_id']
                }
            )

    async def typing_message(self, event):
        await self.send(
            text_data=json.dumps({
                'type': 'typing',
                'sender': event['sender']
            })
        )

    async def chat_message(self, event):
        await self.send(
            text_data=json.dumps({
                'type': 'chat',
                'message': event['message'],
                'sender': event['sender'],
                'time': event['time'],
                'message_id': event['message_id']
            })
        )

    async def read_message(self, event):
        await self.send(
            text_data=json.dumps({
                'type': 'read',
                'message_id': event['message_id']
            })
        )