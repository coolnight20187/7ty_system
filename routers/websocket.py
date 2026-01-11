# websocket.py
from fastapi import WebSocket, WebSocketDisconnect, Depends, Query
from typing import Dict, List, Optional
from datetime import datetime
import json
import asyncio
import uuid

from database import get_db
from models import User, Notification
from dependencies import get_current_user_ws

class ConnectionManager:
    """Quản lý kết nối WebSocket"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_connections: Dict[int, List[str]] = {}
        self.room_connections: Dict[str, List[str]] = {
            "admin": [],
            "agents": [],
            "support": []
        }
    
    async def connect(self, websocket: WebSocket, user_id: int, client_id: str):
        """Kết nối WebSocket"""
        await websocket.accept()
        
        self.active_connections[client_id] = websocket
        
        if user_id not in self.user_connections:
            self.user_connections[user_id] = []
        
        self.user_connections[user_id].append(client_id)
        
        # Thêm vào room dựa trên role
        # (Cần lấy thông tin user từ database)
        
        return client_id
    
    def disconnect(self, client_id: str, user_id: int = None):
        """Ngắt kết nối WebSocket"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        
        if user_id and user_id in self.user_connections:
            if client_id in self.user_connections[user_id]:
                self.user_connections[user_id].remove(client_id)
            
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        
        # Xóa khỏi tất cả rooms
        for room in self.room_connections.values():
            if client_id in room:
                room.remove(client_id)
    
    async def send_personal_message(self, message: dict, client_id: str):
        """Gửi tin nhắn cho một client cụ thể"""
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_json(message)
            except Exception:
                # Client đã ngắt kết nối
                pass
    
    async def send_to_user(self, message: dict, user_id: int):
        """Gửi tin nhắn cho tất cả client của một user"""
        if user_id in self.user_connections:
            for client_id in self.user_connections[user_id]:
                await self.send_personal_message(message, client_id)
    
    async def broadcast(self, message: dict):
        """Gửi tin nhắn cho tất cả client"""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Broadcasting to {len(self.active_connections)} clients: {message.get('type')}")
        sent_count = 0
        for client_id in list(self.active_connections.keys()):
            try:
                await self.send_personal_message(message, client_id)
                sent_count += 1
            except Exception as e:
                logger.warning(f"Failed to send to client {client_id}: {e}")
        logger.info(f"Broadcast completed: {sent_count} clients received message")
    
    async def send_to_room(self, message: dict, room: str):
        """Gửi tin nhắn cho tất cả client trong room"""
        if room in self.room_connections:
            for client_id in self.room_connections[room]:
                await self.send_personal_message(message, client_id)
    
    def get_connected_users(self) -> List[int]:
        """Lấy danh sách user đang kết nối"""
        return list(self.user_connections.keys())
    
    def get_connection_count(self) -> int:
        """Lấy số lượng kết nối đang hoạt động"""
        return len(self.active_connections)

# Tạo instance của ConnectionManager
manager = ConnectionManager()

# WebSocket endpoint chính
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    client_id: Optional[str] = Query(None)
):
    """Endpoint WebSocket chính"""
    user = None
    db = next(get_db())
    
    try:
        # Xác thực user
        if token:
            user = await get_current_user_ws(token, db)
        
        # Tạo client_id nếu không có
        if not client_id:
            client_id = str(uuid.uuid4())
        
        # Kết nối
        user_id = user.id if user else 0
        await manager.connect(websocket, user_id, client_id)
        
        # Gửi thông báo kết nối thành công
        await manager.send_personal_message({
            "type": "connection_established",
            "client_id": client_id,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
            "message": "Kết nối WebSocket thành công"
        }, client_id)
        
        # Gửi thông tin kết nối hiện tại (chỉ cho admin)
        if user and user.role == "admin":
            await manager.send_personal_message({
                "type": "connection_stats",
                "total_connections": manager.get_connection_count(),
                "connected_users": manager.get_connected_users(),
                "timestamp": datetime.now().isoformat()
            }, client_id)
        
        # Lắng nghe tin nhắn từ client
        try:
            while True:
                data = await websocket.receive_text()
                
                try:
                    message = json.loads(data)
                    await handle_websocket_message(message, client_id, user, db)
                    
                except json.JSONDecodeError:
                    await manager.send_personal_message({
                        "type": "error",
                        "message": "Tin nhắn không hợp lệ",
                        "timestamp": datetime.now().isoformat()
                    }, client_id)
                    
        except WebSocketDisconnect:
            # Client ngắt kết nối
            manager.disconnect(client_id, user.id if user else None)
            
            # Thông báo cho admin
            if user and user.role == "admin":
                await manager.send_to_room({
                    "type": "user_disconnected",
                    "user_id": user.id,
                    "username": user.username,
                    "client_id": client_id,
                    "timestamp": datetime.now().isoformat()
                }, "admin")
                
    except Exception as e:
        # Xử lý lỗi
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Lỗi kết nối: {str(e)}",
                "timestamp": datetime.now().isoformat()
            })
        except:
            pass
        
        manager.disconnect(client_id, user.id if user else None)
        
    finally:
        if db:
            db.close()

async def handle_websocket_message(message: dict, client_id: str, user, db):
    """Xử lý tin nhắn từ WebSocket client"""
    message_type = message.get("type")
    
    if not message_type:
        await manager.send_personal_message({
            "type": "error",
            "message": "Thiếu trường 'type' trong tin nhắn",
            "timestamp": datetime.now().isoformat()
        }, client_id)
        return
    
    # Xử lý theo loại tin nhắn
    if message_type == "ping":
        await manager.send_personal_message({
            "type": "pong",
            "timestamp": datetime.now().isoformat()
        }, client_id)
    
    elif message_type == "chat_message":
        await handle_chat_message(message, client_id, user, db)
    
    elif message_type == "notification":
        await handle_notification_message(message, client_id, user, db)
    
    elif message_type == "system_command":
        await handle_system_command(message, client_id, user, db)
    
    elif message_type == "subscribe":
        await handle_subscription(message, client_id, user, db)
    
    elif message_type == "unsubscribe":
        await handle_unsubscription(message, client_id, user, db)
    
    else:
        await manager.send_personal_message({
            "type": "error",
            "message": f"Loại tin nhắn không được hỗ trợ: {message_type}",
            "timestamp": datetime.now().isoformat()
        }, client_id)

async def handle_chat_message(message: dict, client_id: str, user, db):
    """Xử lý tin nhắn chat"""
    if not user:
        await manager.send_personal_message({
            "type": "error",
            "message": "Cần đăng nhập để gửi tin nhắn chat",
            "timestamp": datetime.now().isoformat()
        }, client_id)
        return
    
    content = message.get("content", "").strip()
    recipient_id = message.get("recipient_id")
    room = message.get("room")
    
    if not content:
        await manager.send_personal_message({
            "type": "error",
            "message": "Nội dung tin nhắn không được để trống",
            "timestamp": datetime.now().isoformat()
        }, client_id)
        return
    
    # Tạo tin nhắn chat
    chat_message = {
        "type": "chat_message",
        "message_id": str(uuid.uuid4()),
        "sender_id": user.id,
        "sender_name": user.username,
        "content": content,
        "timestamp": datetime.now().isoformat()
    }
    
    # Gửi tin nhắn
    if recipient_id:
        # Tin nhắn riêng tư
        chat_message["recipient_id"] = recipient_id
        
        # Gửi cho người nhận
        await manager.send_to_user(chat_message, recipient_id)
        
        # Gửi lại cho người gửi (để confirm)
        await manager.send_personal_message(chat_message, client_id)
        
        # Lưu vào database (nếu cần)
        # ...
        
    elif room:
        # Tin nhắn trong room
        chat_message["room"] = room
        
        # Gửi cho tất cả client trong room
        await manager.send_to_room(chat_message, room)
        
        # Lưu vào database (nếu cần)
        # ...
        
    else:
        # Broadcast (chỉ admin)
        if user.role == "admin":
            await manager.broadcast(chat_message)
        else:
            await manager.send_personal_message({
                "type": "error",
                "message": "Chỉ admin mới có thể gửi tin nhắn broadcast",
                "timestamp": datetime.now().isoformat()
            }, client_id)

async def handle_notification_message(message: dict, client_id: str, user, db):
    """Xử lý tin nhắn thông báo"""
    if not user or user.role != "admin":
        await manager.send_personal_message({
            "type": "error",
            "message": "Chỉ admin mới có thể gửi thông báo",
            "timestamp": datetime.now().isoformat()
        }, client_id)
        return
    
    title = message.get("title", "").strip()
    content = message.get("content", "").strip()
    notification_type = message.get("notification_type", "info")
    target_users = message.get("target_users", [])  # Danh sách user_id
    
    if not title or not content:
        await manager.send_personal_message({
            "type": "error",
            "message": "Tiêu đề và nội dung thông báo không được để trống",
            "timestamp": datetime.now().isoformat()
        }, client_id)
        return
    
    # Tạo thông báo
    notification = {
        "type": "notification",
        "notification_id": str(uuid.uuid4()),
        "title": title,
        "content": content,
        "notification_type": notification_type,
        "timestamp": datetime.now().isoformat()
    }
    
    # Gửi thông báo
    if target_users:
        # Gửi cho user cụ thể
        for user_id in target_users:
            await manager.send_to_user(notification, user_id)
    else:
        # Gửi cho tất cả user
        for user_id in manager.get_connected_users():
            await manager.send_to_user(notification, user_id)
    
    # Lưu vào database
    db_notification = Notification(
        title=title,
        content=content,
        notification_type=notification_type,
        target_users=json.dumps(target_users) if target_users else None,
        created_by=user.id
    )
    
    db.add(db_notification)
    db.commit()
    
    # Xác nhận
    await manager.send_personal_message({
        "type": "notification_sent",
        "notification_id": notification["notification_id"],
        "timestamp": datetime.now().isoformat()
    }, client_id)

async def handle_system_command(message: dict, client_id: str, user, db):
    """Xử lý lệnh hệ thống"""
    if not user or user.role != "admin":
        await manager.send_personal_message({
            "type": "error",
            "message": "Chỉ admin mới có thể thực hiện lệnh hệ thống",
            "timestamp": datetime.now().isoformat()
        }, client_id)
        return
    
    command = message.get("command", "").strip()
    
    if command == "get_connections":
        # Lấy thông tin kết nối
        await manager.send_personal_message({
            "type": "connection_info",
            "total_connections": manager.get_connection_count(),
            "connected_users": manager.get_connected_users(),
            "timestamp": datetime.now().isoformat()
        }, client_id)
    
    elif command == "broadcast_message":
        # Gửi tin nhắn broadcast
        broadcast_content = message.get("content", "").strip()
        
        if broadcast_content:
            await manager.broadcast({
                "type": "system_broadcast",
                "content": broadcast_content,
                "timestamp": datetime.now().isoformat()
            })
    
    elif command == "reload_settings":
        # Tải lại cài đặt
        await manager.broadcast({
            "type": "system_reload",
            "message": "Hệ thống đang tải lại cài đặt",
            "timestamp": datetime.now().isoformat()
        })
    
    else:
        await manager.send_personal_message({
            "type": "error",
            "message": f"Lệnh không được hỗ trợ: {command}",
            "timestamp": datetime.now().isoformat()
        }, client_id)

async def handle_subscription(message: dict, client_id: str, user, db):
    """Xử lý đăng ký room/channel"""
    if not user:
        await manager.send_personal_message({
            "type": "error",
            "message": "Cần đăng nhập để đăng ký",
            "timestamp": datetime.now().isoformat()
        }, client_id)
        return
    
    room = message.get("room", "").strip()
    
    if not room:
        await manager.send_personal_message({
            "type": "error",
            "message": "Thiếu tên room",
            "timestamp": datetime.now().isoformat()
        }, client_id)
        return
    
    # Kiểm tra quyền truy cập room
    if room == "admin" and user.role != "admin":
        await manager.send_personal_message({
            "type": "error",
            "message": "Không có quyền truy cập room admin",
            "timestamp": datetime.now().isoformat()
        }, client_id)
        return
    
    # Thêm vào room
    if room not in manager.room_connections:
        manager.room_connections[room] = []
    
    if client_id not in manager.room_connections[room]:
        manager.room_connections[room].append(client_id)
    
    await manager.send_personal_message({
        "type": "subscribed",
        "room": room,
        "timestamp": datetime.now().isoformat(),
        "message": f"Đã đăng ký room: {room}"
    }, client_id)

async def handle_unsubscription(message: dict, client_id: str, user, db):
    """Xử lý hủy đăng ký room/channel"""
    room = message.get("room", "").strip()
    
    if room:
        # Hủy đăng ký room cụ thể
        if room in manager.room_connections and client_id in manager.room_connections[room]:
            manager.room_connections[room].remove(client_id)
            
            await manager.send_personal_message({
                "type": "unsubscribed",
                "room": room,
                "timestamp": datetime.now().isoformat(),
                "message": f"Đã hủy đăng ký room: {room}"
            }, client_id)
    else:
        # Hủy đăng ký tất cả rooms
        for room_name in list(manager.room_connections.keys()):
            if client_id in manager.room_connections[room_name]:
                manager.room_connections[room_name].remove(client_id)

# Hàm gửi thông báo realtime
async def send_realtime_notification(
    user_id: int,
    title: str,
    content: str,
    notification_type: str = "info",
    data: dict = None
):
    """Gửi thông báo realtime cho user"""
    notification = {
        "type": "realtime_notification",
        "notification_id": str(uuid.uuid4()),
        "title": title,
        "content": content,
        "notification_type": notification_type,
        "timestamp": datetime.now().isoformat(),
        "data": data or {}
    }
    
    await manager.send_to_user(notification, user_id)

# Hàm gửi thông báo cho tất cả admin
async def notify_admins(title: str, content: str, notification_type: str = "info"):
    """Gửi thông báo cho tất cả admin đang online"""
    notification = {
        "type": "admin_notification",
        "notification_id": str(uuid.uuid4()),
        "title": title,
        "content": content,
        "notification_type": notification_type,
        "timestamp": datetime.now().isoformat()
    }
    
    await manager.send_to_room(notification, "admin")

# Hàm gửi thông báo cho tất cả đại lý
async def notify_agents(title: str, content: str, notification_type: str = "info"):
    """Gửi thông báo cho tất cả đại lý đang online"""
    notification = {
        "type": "agent_notification",
        "notification_id": str(uuid.uuid4()),
        "title": title,
        "content": content,
        "notification_type": notification_type,
        "timestamp": datetime.now().isoformat()
    }
    
    await manager.send_to_room(notification, "agents")

# Hàm kiểm tra trạng thái kết nối của user
def is_user_online(user_id: int) -> bool:
    """Kiểm tra xem user có đang online không"""
    return user_id in manager.user_connections

# Hàm lấy số lượng user đang online
def get_online_users_count() -> int:
    """Lấy số lượng user đang online"""
    return len(manager.user_connections)

# Hàm lấy số lượng kết nối đang hoạt động
def get_active_connections_count() -> int:
    """Lấy số lượng kết nối đang hoạt động"""
    return manager.get_connection_count()

# Background task để gửi ping định kỳ
async def send_periodic_pings():
    """Gửi ping định kỳ để giữ kết nối"""
    while True:
        try:
            # Gửi ping cho tất cả client
            await manager.broadcast({
                "type": "ping",
                "timestamp": datetime.now().isoformat()
            })
            
            # Đợi 30 giây
            await asyncio.sleep(30)
            
        except Exception as e:
            print(f"Lỗi khi gửi ping: {e}")
            await asyncio.sleep(30)

# Background task để kiểm tra kết nối chết
async def cleanup_dead_connections():
    """Dọn dẹp kết nối chết"""
    while True:
        try:
            # Kiểm tra và dọn dẹp mỗi 5 phút
            await asyncio.sleep(300)
            
            # Trong thực tế, bạn có thể thêm logic kiểm tra
            # client nào không phản hồi ping
            
        except Exception as e:
            print(f"Lỗi khi dọn dẹp kết nối: {e}")
            await asyncio.sleep(300)