# 📱 안드로이드 서버 모니터링 앱 (GitHub Actions용)
# GitHub에서 자동 빌드됩니다

import json
import time
import threading
import requests
from datetime import datetime
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.switch import Switch
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivymd.app import MDApp
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.button import MDRaisedButton, MDIconButton
from kivymd.uix.switch import MDSwitch
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.screen import MDScreen
from kivymd.uix.screenmanager import MDScreenManager
try:
    from plyer import notification, vibrator
except ImportError:
    print("[경고] plyer 모듈을 찾을 수 없습니다. 알림 기능이 제한됩니다.")
    notification = None
    vibrator = None
import os

# 기본 설정
DEFAULT_CONFIG = {
    "servers": [
        {
            "name": "Google 테스트",
            "url": "https://www.google.com",
            "monitor": True,
            "status": "알 수 없음"
        },
        {
            "name": "GitHub 테스트",
            "url": "https://github.com",
            "monitor": True,
            "status": "알 수 없음"
        },
        {
            "name": "네이버 테스트",
            "url": "https://www.naver.com",
            "monitor": False,
            "status": "알 수 없음"
        }
    ],
    "check_interval": 10,
    "alert_interval": 60,
    "notification_enabled": True,
    "vibration_enabled": True
}

class ServerMonitorApp(MDApp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.theme_cls.theme_style = "Light"
        self.theme_cls.primary_palette = "Blue"
        
        # 설정 로드
        self.config = self.load_config()
        self.server_list = self.config["servers"]
        self.check_interval = self.config.get("check_interval", 10)
        self.alert_interval = self.config.get("alert_interval", 60)
        self.notification_enabled = self.config.get("notification_enabled", True)
        self.vibration_enabled = self.config.get("vibration_enabled", True)
        
        # 모니터링 관련 변수
        self.last_alert_times = [0 for _ in self.server_list]
        self.previous_status = {}
        for i, server in enumerate(self.server_list):
            self.previous_status[i] = "알 수 없음"
        
        # 모니터링 스레드
        self.monitoring_thread = None
        self.monitoring_active = False
        
        # UI 컴포넌트
        self.server_cards = []
        self.status_label = None
        
    def build(self):
        """앱 UI 빌드"""
        self.title = "🔍 서버 모니터링"
        
        # 메인 화면 매니저
        sm = MDScreenManager()
        
        # 메인 화면
        main_screen = MDScreen(name="main")
        main_layout = MDBoxLayout(orientation="vertical", padding="10dp", spacing="10dp")
        
        # 상단 툴바
        toolbar = MDTopAppBar(
            title="🔍 서버 모니터링",
            elevation=10,
            left_action_items=[["menu", lambda x: self.open_settings()]],
            right_action_items=[
                ["refresh", lambda x: self.manual_refresh()],
                ["bell", lambda x: self.toggle_notifications()]
            ]
        )
        main_layout.add_widget(toolbar)
        
        # 상태 요약 카드
        self.status_card = self.create_status_card()
        main_layout.add_widget(self.status_card)
        
        # 전체 제어 카드
        control_card = self.create_control_card()
        main_layout.add_widget(control_card)
        
        # 서버 목록 스크롤뷰
        scroll = ScrollView()
        self.server_container = MDBoxLayout(
            orientation="vertical",
            spacing="10dp",
            adaptive_height=True
        )
        scroll.add_widget(self.server_container)
        main_layout.add_widget(scroll)
        
        # 서버 카드들 생성
        self.create_server_cards()
        
        main_screen.add_widget(main_layout)
        sm.add_widget(main_screen)
        
        # 모니터링 시작
        self.start_monitoring()
        
        # UI 업데이트 스케줄
        Clock.schedule_interval(self.update_ui, 2)
        
        return sm
    
    def create_status_card(self):
        """상태 요약 카드 생성"""
        card = MDCard(
            size_hint_y=None,
            height="80dp",
            padding="15dp",
            elevation=3,
            md_bg_color=[0.9, 0.95, 1, 1]
        )
        
        layout = MDBoxLayout(orientation="horizontal", spacing="10dp")
        
        self.status_label = MDLabel(
            text="📊 상태 확인 중...",
            theme_text_color="Primary",
            font_style="Subtitle1",
            size_hint_x=0.8
        )
        layout.add_widget(self.status_label)
        
        # 새로고침 버튼
        refresh_btn = MDIconButton(
            icon="refresh",
            theme_icon_color="Primary",
            size_hint_x=0.2,
            on_release=lambda x: self.manual_refresh()
        )
        layout.add_widget(refresh_btn)
        
        card.add_widget(layout)
        return card
    
    def create_control_card(self):
        """전체 제어 카드 생성"""
        card = MDCard(
            size_hint_y=None,
            height="120dp",
            padding="15dp",
            elevation=3
        )
        
        layout = MDGridLayout(cols=2, spacing="10dp")
        
        # 전체 ON 버튼
        all_on_btn = MDRaisedButton(
            text="🟢 전체 ON",
            md_bg_color=[0.2, 0.8, 0.2, 1],
            size_hint_y=None,
            height="40dp",
            on_release=lambda x: self.set_all_monitoring(True)
        )
        layout.add_widget(all_on_btn)
        
        # 전체 OFF 버튼
        all_off_btn = MDRaisedButton(
            text="🔴 전체 OFF",
            md_bg_color=[0.8, 0.2, 0.2, 1],
            size_hint_y=None,
            height="40dp",
            on_release=lambda x: self.set_all_monitoring(False)
        )
        layout.add_widget(all_off_btn)
        
        # 알림 테스트 버튼
        test_btn = MDRaisedButton(
            text="🔔 알림 테스트",
            md_bg_color=[0.2, 0.6, 0.8, 1],
            size_hint_y=None,
            height="40dp",
            on_release=lambda x: self.test_notification()
        )
        layout.add_widget(test_btn)
        
        # 설정 버튼
        settings_btn = MDRaisedButton(
            text="⚙️ 설정",
            md_bg_color=[0.6, 0.6, 0.6, 1],
            size_hint_y=None,
            height="40dp",
            on_release=lambda x: self.open_settings()
        )
        layout.add_widget(settings_btn)
        
        card.add_widget(layout)
        return card
    
    def create_server_cards(self):
        """서버 카드들 생성"""
        self.server_cards = []
        
        for i, server in enumerate(self.server_list):
            card = self.create_server_card(i, server)
            self.server_cards.append(card)
            self.server_container.add_widget(card)
    
    def create_server_card(self, index, server):
        """개별 서버 카드 생성"""
        card = MDCard(
            size_hint_y=None,
            height="120dp",
            padding="15dp",
            elevation=2,
            md_bg_color=[1, 1, 1, 1]
        )
        
        layout = MDBoxLayout(orientation="vertical", spacing="5dp")
        
        # 서버명과 상태
        header_layout = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="30dp")
        
        server_name = MDLabel(
            text=f"📡 {server['name']}",
            theme_text_color="Primary",
            font_style="Subtitle2",
            size_hint_x=0.7
        )
        header_layout.add_widget(server_name)
        
        # 상태 표시
        status_label = MDLabel(
            text="❓ 확인중",
            theme_text_color="Secondary",
            font_style="Caption",
            size_hint_x=0.3,
            halign="right"
        )
        header_layout.add_widget(status_label)
        
        layout.add_widget(header_layout)
        
        # URL 표시
        url_label = MDLabel(
            text=f"🔗 {server['url']}",
            theme_text_color="Hint",
            font_style="Caption",
            size_hint_y=None,
            height="20dp"
        )
        layout.add_widget(url_label)
        
        # 감시 스위치
        switch_layout = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="40dp")
        
        switch_label = MDLabel(
            text="👁️ 감시하기",
            theme_text_color="Primary",
            font_style="Body2",
            size_hint_x=0.7
        )
        switch_layout.add_widget(switch_label)
        
        monitor_switch = MDSwitch(
            active=server['monitor'],
            size_hint_x=0.3,
            on_active=lambda switch, active, idx=index: self.toggle_server_monitoring(idx, active)
        )
        switch_layout.add_widget(monitor_switch)
        
        layout.add_widget(switch_layout)
        
        card.add_widget(layout)
        
        # 카드에 참조 저장
        card.status_label = status_label
        card.monitor_switch = monitor_switch
        card.server_index = index
        
        return card
    
    def load_config(self):
        """설정 파일 로드"""
        try:
            if os.path.exists("config.json"):
                with open("config.json", "r", encoding="utf-8") as f:
                    return json.load(f)
            else:
                return DEFAULT_CONFIG.copy()
        except Exception as e:
            print(f"[설정 로드 오류] {e}")
            return DEFAULT_CONFIG.copy()
    
    def save_config(self):
        """설정 파일 저장"""
        try:
            self.config["servers"] = self.server_list
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            print("[설정 저장됨]")
        except Exception as e:
            print(f"[설정 저장 실패] {e}")
    
    def check_server_status(self, server):
        """서버 상태 확인"""
        try:
            response = requests.get(server["url"], timeout=10)
            if response.status_code == 200:
                return "온라인"
            else:
                return f"오류 ({response.status_code})"
        except requests.exceptions.Timeout:
            return "타임아웃"
        except requests.exceptions.ConnectionError:
            return "연결 실패"
        except Exception as e:
            return f"오류: {str(e)[:20]}"
    
    def start_monitoring(self):
        """모니터링 시작"""
        if not self.monitoring_active:
            self.monitoring_active = True
            self.monitoring_thread = threading.Thread(target=self.monitor_servers, daemon=True)
            self.monitoring_thread.start()
            print("[모니터링 시작]")
    
    def stop_monitoring(self):
        """모니터링 중지"""
        self.monitoring_active = False
        print("[모니터링 중지]")
    
    def monitor_servers(self):
        """서버 모니터링 메인 루프"""
        while self.monitoring_active:
            try:
                current_time = time.time()
                
                for i, server in enumerate(self.server_list):
                    if not server.get("monitor", False):
                        continue
                    
                    old_status = server.get("status", "알 수 없음")
                    new_status = self.check_server_status(server)
                    server["status"] = new_status
                    
                    # 상태 변화 감지
                    if self.previous_status[i] != new_status:
                        print(f"[상태 변경] {server['name']}: {self.previous_status[i]} → {new_status}")
                        self.previous_status[i] = new_status
                        
                        # 상태 변경 시 알림
                        if old_status != "알 수 없음":
                            self.send_notification(server['name'], old_status, new_status)
                            self.last_alert_times[i] = current_time
                
                time.sleep(self.check_interval)
                
            except Exception as e:
                print(f"[모니터링 오류] {e}")
                time.sleep(self.check_interval)
    
    def send_notification(self, server_name, old_status, new_status):
        """상태 변경 알림 전송"""
        if not self.notification_enabled or not notification:
            return
        
        try:
            if new_status == "온라인":
                title = "✅ 서버 복구"
                message = f"{server_name}\n{old_status} → {new_status}"
                
                # 진동 (복구 시 짧게)
                if self.vibration_enabled and vibrator:
                    vibrator.vibrate(0.2)
            else:
                title = "🚨 서버 문제"
                message = f"{server_name}\n{old_status} → {new_status}"
                
                # 진동 (문제 시 길게)
                if self.vibration_enabled and vibrator:
                    vibrator.vibrate(0.5)
            
            notification.notify(
                title=title,
                message=message,
                app_name="서버 모니터링",
                timeout=10
            )
            
            print(f"[알림 발송] {title}: {message}")
            
        except Exception as e:
            print(f"[알림 오류] {e}")
    
    def update_ui(self, dt):
        """UI 업데이트"""
        try:
            # 상태 요약 업데이트
            online_count = sum(1 for s in self.server_list if s['status'] == '온라인' and s['monitor'])
            monitor_count = sum(1 for s in self.server_list if s['monitor'])
            problem_count = sum(1 for s in self.server_list if s['status'] not in ['온라인', '알 수 없음'] and s['monitor'])
            
            if problem_count > 0:
                status_text = f"⚠️ 문제: {problem_count}개 | 온라인: {online_count}/{monitor_count}"
            else:
                status_text = f"📊 온라인: {online_count}/{monitor_count} | 🕐 {datetime.now().strftime('%H:%M:%S')}"
            
            self.status_label.text = status_text
            
            # 서버 카드 업데이트
            for i, card in enumerate(self.server_cards):
                server = self.server_list[i]
                status = server['status']
                
                # 상태별 아이콘과 색상
                if status == "온라인":
                    status_text = "🟢 온라인"
                    card.md_bg_color = [0.9, 1, 0.9, 1]
                elif status in ["연결 실패", "타임아웃"]:
                    status_text = f"🔴 {status}"
                    card.md_bg_color = [1, 0.9, 0.9, 1]
                else:
                    status_text = f"❓ {status}"
                    card.md_bg_color = [1, 1, 0.9, 1]
                
                card.status_label.text = status_text
                card.monitor_switch.active = server['monitor']
            
        except Exception as e:
            print(f"[UI 업데이트 오류] {e}")
    
    def toggle_server_monitoring(self, index, active):
        """개별 서버 모니터링 토글"""
        try:
            self.server_list[index]['monitor'] = active
            self.save_config()
            print(f"[설정] {self.server_list[index]['name']} 감시: {active}")
        except Exception as e:
            print(f"[토글 오류] {e}")
    
    def set_all_monitoring(self, state):
        """전체 서버 모니터링 설정"""
        try:
            for server in self.server_list:
                server['monitor'] = state
            self.save_config()
            print(f"[전체 설정] 감시: {state}")
        except Exception as e:
            print(f"[전체 설정 오류] {e}")
    
    def manual_refresh(self):
        """수동 새로고침"""
        try:
            for i, server in enumerate(self.server_list):
                if server.get("monitor", False):
                    new_status = self.check_server_status(server)
                    server["status"] = new_status
                    self.previous_status[i] = new_status
            
            print("[수동 새로고침 완료]")
        except Exception as e:
            print(f"[새로고침 오류] {e}")
    
    def test_notification(self):
        """알림 테스트"""
        try:
            if notification:
                notification.notify(
                    title="🔔 테스트 알림",
                    message="서버 모니터링 앱이 정상 작동중입니다!",
                    app_name="서버 모니터링",
                    timeout=5
                )
                
                if self.vibration_enabled and vibrator:
                    vibrator.vibrate(0.2)
                
                print("[알림 테스트 완료]")
            else:
                print("[알림 모듈 없음]")
        except Exception as e:
            print(f"[알림 테스트 오류] {e}")
    
    def toggle_notifications(self):
        """알림 토글"""
        self.notification_enabled = not self.notification_enabled
        self.config["notification_enabled"] = self.notification_enabled
        self.save_config()
        
        status = "활성화" if self.notification_enabled else "비활성화"
        print(f"[알림 {status}]")
    
    def open_settings(self):
        """설정 창 열기"""
        popup_content = MDBoxLayout(orientation="vertical", spacing="10dp", padding="20dp")
        
        # 알림 설정
        notification_layout = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="50dp")
        notification_label = MDLabel(text="🔔 푸시 알림", size_hint_x=0.7)
        notification_switch = MDSwitch(
            active=self.notification_enabled,
            size_hint_x=0.3,
            on_active=lambda switch, active: self.set_notification_enabled(active)
        )
        notification_layout.add_widget(notification_label)
        notification_layout.add_widget(notification_switch)
        popup_content.add_widget(notification_layout)
        
        # 진동 설정
        vibration_layout = MDBoxLayout(orientation="horizontal", size_hint_y=None, height="50dp")
        vibration_label = MDLabel(text="📳 진동 알림", size_hint_x=0.7)
        vibration_switch = MDSwitch(
            active=self.vibration_enabled,
            size_hint_x=0.3,
            on_active=lambda switch, active: self.set_vibration_enabled(active)
        )
        vibration_layout.add_widget(vibration_label)
        vibration_layout.add_widget(vibration_switch)
        popup_content.add_widget(vibration_layout)
        
        # 체크 간격 설정
        interval_label = MDLabel(text=f"⏱️ 체크 간격: {self.check_interval}초", size_hint_y=None, height="30dp")
        popup_content.add_widget(interval_label)
        
        # 닫기 버튼
        close_btn = MDRaisedButton(
            text="닫기",
            size_hint_y=None,
            height="40dp",
            on_release=lambda x: popup.dismiss()
        )
        popup_content.add_widget(close_btn)
        
        popup = Popup(
            title="⚙️ 설정",
            content=popup_content,
            size_hint=(0.8, 0.6)
        )
        popup.open()
    
    def set_notification_enabled(self, enabled):
        """알림 활성화 설정"""
        self.notification_enabled = enabled
        self.config["notification_enabled"] = enabled
        self.save_config()
    
    def set_vibration_enabled(self, enabled):
        """진동 활성화 설정"""
        self.vibration_enabled = enabled
        self.config["vibration_enabled"] = enabled
        self.save_config()
    
    def on_stop(self):
        """앱 종료 시"""
        self.stop_monitoring()
        self.save_config()

# 앱 실행
if __name__ == "__main__":
    ServerMonitorApp().run()