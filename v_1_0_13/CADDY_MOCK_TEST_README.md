# Caddy API 모의 테스트 가이드

## 개요

Windows 11 로컬 환경에서 실제 Caddy API를 호출하지 않고 도메인 등록/해제 기능을 테스트할 수 있습니다.

`CADDY_MOCK_MODE` 환경 변수를 사용하여 실제 Caddy API 호출과 모의(mock) 테스트를 전환할 수 있습니다.

---

## 사용 방법

### 1️⃣ Windows 로컬에서 모의 테스트 모드 활성화

#### 방법 A: 명령 프롬프트(CMD)에서 실행

```cmd
cd C:\Python\MY_PROJECT\v_1_0_12

REM 환경 변수 설정 (현재 세션에만 적용)
set CADDY_MOCK_MODE=true

REM FastAPI 서버 실행
python -m uvicorn my_main:app --reload --host 127.0.0.1 --port 8000
```

#### 방법 B: PowerShell에서 실행

```powershell
cd C:\Python\MY_PROJECT\v_1_0_12

# 환경 변수 설정 (현재 세션에만 적용)
$env:CADDY_MOCK_MODE="true"

# FastAPI 서버 실행
python -m uvicorn my_main:app --reload --host 127.0.0.1 --port 8000
```

#### 방법 C: VS Code에서 실행 (권장)

`.vscode/launch.json` 파일에 환경 변수를 추가:

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: FastAPI (Mock Mode)",
            "type": "python",
            "request": "launch",
            "module": "uvicorn",
            "args": [
                "my_main:app",
                "--reload",
                "--host", "127.0.0.1",
                "--port", "8000"
            ],
            "env": {
                "CADDY_MOCK_MODE": "true"
            },
            "jinja": true
        }
    ]
}
```

---

### 2️⃣ 모의 모드 확인

서버 시작 시 다음과 같은 메시지가 출력되면 모의 모드가 활성화된 것입니다:

```
============================================================
🎭 [CADDY MOCK MODE 활성화]
   실제 Caddy API를 호출하지 않습니다.
   Windows 로컬 테스트 모드로 동작합니다.
============================================================
```

---

### 3️⃣ 브라우저에서 테스트

1. **웹 브라우저에서 접속**
   ```
   http://127.0.0.1:8000/admin
   ```

2. **로그인 후 도메인 보안 메뉴로 이동**
   ```
   http://127.0.0.1:8000/admin/domain_security
   ```

3. **도메인 등록 테스트**
   - 도메인 입력: `test.example.com`
   - 이메일 입력: `test@example.com`
   - "보안 적용" 버튼 클릭
   - 진행 상황이 실시간으로 표시됩니다 (5단계)
   - 실제 Caddy API를 호출하지 않고 가상 응답을 받습니다

4. **도메인 해제 테스트**
   - "보안 해제" 버튼 클릭
   - 진행 상황이 실시간으로 표시됩니다 (5단계)
   - 실제 Caddy API를 호출하지 않고 가상 응답을 받습니다

---

## 모의 모드 vs 실제 모드 비교

| 구분 | 모의 모드 (CADDY_MOCK_MODE=true) | 실제 모드 (기본값) |
|------|----------------------------------|-------------------|
| **Caddy API 호출** | ❌ 호출하지 않음 | ✅ 실제 호출 |
| **인증서 발급** | 🎭 가상 시뮬레이션 (5초) | 🔐 Let's Encrypt 실제 발급 (최대 10초) |
| **테스트 환경** | 💻 Windows 로컬 | 🌐 Vultr Linux 서버 |
| **Caddy 실행 필요** | ❌ 불필요 | ✅ 필수 |
| **진행 상황 표시** | ✅ SSE로 실시간 표시 | ✅ SSE로 실시간 표시 |
| **메시지 표시** | `[모의]` 접두사 포함 | 일반 메시지 |

---

## 로그 확인

### 모의 모드 로그 예시

```
[Mock Caddy API] 🎭 모의 도메인 등록 시작: test.example.com, 이메일: test@example.com
[Mock Caddy API] 📋 1단계: 가상 Caddy 설정 생성 중...
[Mock Caddy API] 📋 2단계: 가상 Caddy Admin API로 설정 전송 중...
[Mock Caddy API] ✅ 가상 Caddy 설정 적용 성공
[Mock Caddy API] ✅ 가상 도메인 등록 완료: test.example.com
💾 DB 업데이트 시도: admin_id=1, domain=test.example.com, email=test@example.com
✅ DB 업데이트 성공
```

### 실제 모드 로그 예시

```
[Caddy API] 🚀 도메인 등록 함수 시작: example.com, 이메일: admin@example.com
[Caddy API] 📋 1단계: Caddy 설정 생성 중...
[Caddy API] 📋 2단계: Caddy Admin API로 설정 전송 중... (URL: http://127.0.0.1:2019/load)
[Caddy API] 📡 Caddy 응답 코드: 200
[Caddy API] ✅ Caddy 설정 적용 성공
[Caddy API] ✅ 도메인 등록 완료: example.com (인증서 활성화)
```

---

## Vultr Linux 서버에서 실제 모드 사용

Vultr 서버에서는 환경 변수를 설정하지 않으면 자동으로 실제 모드로 동작합니다:

```bash
cd /path/to/project

# 환경 변수 없이 실행 (실제 Caddy API 사용)
python3 -m uvicorn my_main:app --host 0.0.0.0 --port 8000

# 또는 systemd 서비스로 실행 (환경 변수 설정 안 함)
sudo systemctl start my-fastapi-app
```

---

## 주의사항

1. **모의 모드는 테스트 전용입니다**
   - 실제 인증서가 발급되지 않습니다
   - 실제 Caddy 설정이 변경되지 않습니다
   - DB에는 정상적으로 기록됩니다

2. **프로덕션 환경에서는 실제 모드를 사용하세요**
   - Vultr 서버: `CADDY_MOCK_MODE` 환경 변수를 설정하지 마세요
   - Caddy가 실제로 실행 중이어야 합니다

3. **환경 변수 확인**
   ```cmd
   # Windows CMD
   echo %CADDY_MOCK_MODE%

   # Windows PowerShell
   echo $env:CADDY_MOCK_MODE

   # Linux/Mac
   echo $CADDY_MOCK_MODE
   ```

---

## 파일 구조

```
v_1_0_12/
├── my_utilities/
│   ├── my_caddy_api.py           # Caddy API 메인 모듈 (자동 모드 전환)
│   └── my_caddy_api_mock.py      # 모의 테스트 모듈 (새로 추가)
├── my_routers/
│   └── my_domain_security.py     # 도메인 보안 라우터
├── CADDY_MOCK_TEST_README.md     # 이 파일
└── my_main.py                    # FastAPI 메인 앱
```

---

## 문제 해결

### Q1. 모의 모드가 활성화되지 않습니다

**확인 사항:**
- 환경 변수가 제대로 설정되었는지 확인
  ```cmd
  echo %CADDY_MOCK_MODE%
  ```
- 서버를 재시작했는지 확인
- 대소문자를 정확히 `true`로 설정했는지 확인

### Q2. 실제 모드에서 "Caddy 연결 실패" 오류 발생

**해결 방법:**
- Caddy가 실행 중인지 확인
  ```bash
  # Linux
  systemctl status caddy

  # Windows (관리자 권한)
  .\caddy.exe run
  ```
- Caddy Admin API가 `127.0.0.1:2019`에서 실행 중인지 확인

### Q3. DB에 저장된 도메인이 실제와 다릅니다

**설명:**
- 모의 모드에서도 DB에는 정상적으로 저장됩니다
- 테스트 후 DB를 초기화하려면 관리자 설정에서 "초기화" 기능을 사용하세요

---

## 개발자 정보

- **작성일**: 2025-11-09
- **버전**: v_1_0_12
- **모의 모드 추가**: Windows 로컬 테스트 지원
