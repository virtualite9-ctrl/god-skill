# God Skill for Hermes · 근거 기반 인물 증류 엔진

**사람을 흉내 내는 프롬프트가 아니라, 출처로 추적 가능한 인지·결정·표현 구조를 만든다.**

이 저장소는 [fattly/god-skill](https://github.com/fattly/god-skill)을 Hermes Agent에 맞게 포팅한 포크다. 원본의 7차원 인물 증류 방법론은 보존하고 다음을 추가했다.

- Hermes 네이티브 도구 매핑
- 최대 3-lane `delegate_task` wave와 부모 read-back 검증
- raw/research/final 분리 및 resumable `run-state.json`
- source ledger와 `[S###]` claim traceability
- 살아 있는 사람·사적 인물·실제 미성년자에 대한 fail-closed privacy/동의 규칙
- 독립 calibration·boundary·voice·soul-layer QA
- stdlib-only 정적 validator와 단위 테스트
- 생성 결과를 Hermes user-local skill로 설치·검증하는 절차

## 설치

Hermes의 제3자 GitHub 설치 경로를 사용한다. 먼저 security scan 결과를 확인한다.

```bash
hermes skills inspect https://raw.githubusercontent.com/virtualite9-ctrl/god-skill/main/SKILL.md
hermes skills install --category research https://raw.githubusercontent.com/virtualite9-ctrl/god-skill/main/SKILL.md
```

설치 후 새 세션에서:

```text
/god-skill 이순신을 근거 기반으로 증류해
/god-skill distill Ada Lovelace
/god-skill 上帝造人 李小龙
```

Hermes CLI로 명시 로드할 수도 있다.

```bash
hermes --skills god-skill
```

## 기본 산출물

```text
<slug>-perspective/
├── SKILL.md
├── run-state.json
├── references/
│   ├── source-ledger.md
│   ├── source-index.md
│   ├── research/general/G1-conversations.md
│   ├── research/general/G2-expression-dna.md
│   ├── research/general/G3-external-views.md
│   ├── research/general/G4-timeline.md
│   ├── research/general/G5-soul-layer.md 또는 G5-omission.md
│   └── research/specialist/A?-<domain>.md
└── validation/
    ├── calibration.md
    ├── boundary.md
    ├── voice-blind-test.md
    └── final-scorecard.md
```

## 실행 원칙

1. 사용자가 파일·URL을 주면 그 원자료를 먼저 읽는다.
2. 사실, 본인 진술, 타인 평가, 실제 행동, 연구자 추론을 구분한다.
3. 모순을 지우지 않고 시간·맥락·출처 수준에 따라 보존한다.
4. 영혼층은 진단이 아니라 반증 가능한 해석이며, source ID·반례·신뢰도가 필수다.
5. child Agent의 성공 문구를 믿지 않고 부모가 산출물을 실제로 읽는다.
6. static validator와 독립 QA를 통과하기 전에는 생성 skill을 설치하지 않는다.
7. 설치본에는 sanitized source index만 포함하고 내부 원장·raw 자료·validation·절대 로컬 경로를 제외한다.

## 검증

저장소 테스트:

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile scripts/validate_persona_skill.py
```

현재 회귀 suite는 정상 경로와 real-minor 차단, private G5 생략, source-count 위조, QA hash 위조, 긴 인용, 절대 경로, malformed YAML/UTF-8, decoy 입력을 포함한 15개 사례를 검사한다.

생성된 인물 프로젝트:

```bash
python3 scripts/validate_persona_skill.py /absolute/path/to/person-perspective --json
```

초안 상태만 점검할 때:

```bash
python3 scripts/validate_persona_skill.py /path/to/draft --draft --json
```

## 파일 안내

- [`SKILL.md`](SKILL.md): Hermes용 실행 코어
- [`references/hermes-execution.md`](references/hermes-execution.md): delegation brief, state schema, resume·설치 규약
- [`templates/persona-skill.md`](templates/persona-skill.md): 생성할 인물 skill 템플릿
- [`templates/validation-artifact.md`](templates/validation-artifact.md): 독립 reviewer ID·artifact hash·hard-fail 계약
- [`scripts/validate_persona_skill.py`](scripts/validate_persona_skill.py): 최종 산출물 정적 검증기
- [`references/upstream-methodology.md`](references/upstream-methodology.md): 원본 Phase 0–2 및 G/A Agent 정의
- [`references/upstream-persona-template.md`](references/upstream-persona-template.md): 원본 생성 템플릿과 예시
- [`references/upstream-validation-and-edge-cases.md`](references/upstream-validation-and-edge-cases.md): 원본 QA·갱신·특수 상황 규칙

## 안전 경계

- 실제 미성년자의 심층 증류 금지; 비공개 개인은 명시적 동의와 soul-layer 비활성화가 필수
- 정신건강, 질병, 성적 지향, 종교, 정치 성향 등 비공개 민감 속성 추론 금지
- 채용·보험·수사·의료·법률·금융의 중대한 자동 의사결정에 사용 금지
- 공개 자료의 긴 전문 복제 대신 짧은 인용과 정확한 위치 메타데이터 사용
- “그 사람이 실제로 이렇게 말한다”가 아니라 “검증된 자료에서 추출한 프레임이라면”으로 표현

## Upstream과 라이선스

- Upstream: [fattly/god-skill](https://github.com/fattly/god-skill)
- Fork: [virtualite9-ctrl/god-skill](https://github.com/virtualite9-ctrl/god-skill)
- 기반 commit: `72fed112e9c390406e8463489f0b2a05b7160e8a`
- License: MIT

원본 방법론과 예시는 upstream 저작자 `fattly`에 귀속된다. Hermes 포팅·검증 도구·안전 규칙은 이 포크의 변경사항이다.
