추적 중단 항목

* app/build.gradle.kts: 빌드 설정 파일로 특정 컴포넌트 진입점이 아님
* GroupMembersDialog.java: 파일 삭제됨
* NameColor.kt: 단순 데이터 클래스
* MessageRecord.java: 광범위 참조 모델 클래스
* RecipientRecord.kt: 광범위 참조 모델 클래스
* GroupInsufficientRightsException.java: 단순 예외 클래스
* MemberLabel.kt: 앱 전반 공통 데이터 모델
* GroupMemberEntry.java: UI용 데이터 모델
* Recipient.kt: 광범위 참조 모델 클래스
* RecipientCreator.kt: 공통 유틸리티 클래스
* BackupUtil.java: 단순 어노테이션 추가
* Environment.kt: 전역 환경 설정 유틸리티
* RemoteConfig.kt: 전역 설정 싱글톤
* Database.proto: 프로토콜 정의 파일
* megaphone_backup_media_size.xml (Night/Base): 정적 이미지 리소스
* megaphone_backup_message_count.xml (Night/Base): 정적 이미지 리소스
* megaphone_backup_storage_low.xml (Night/Base): 정적 이미지 리소스
* ic_group_solid_highlight_24.xml: 리소스 삭제됨
* conversation_group_options.xml: 리소스 삭제됨
* app/static-ips.gradle.kts: 네트워크 인프라 설정 파일
* build.gradle.kts: 빌드 자동화 설정 파일
* gradle/libs.versions.toml: 의존성 정의 파일
* gradle/verification-metadata.xml: 의존성 무결성 검증 파일

### Background / Database

| 확인 | 위험도 | 트리거 | 진입점 | 테스트 시나리오 | 대상 파일 |
|------|--------|--------|--------|----------------|-----------|
| [ ] | CRITICAL | BG(Database Schema Update / Recipient Settings) | `SignalDatabase.kt` | DB 마이그레이션 후 통화 및 답장 알림 설정 컬럼 생성 및 기본값 확인 | `RecipientTable.kt` |
| [ ] | CRITICAL | BG(Database Migration) | `SignalDatabase.kt` | 앱 업데이트 시 V304 마이그레이션이 에러 없이 304 버전으로 업그레이드되는지 확인 | `SignalDatabaseMigrations.kt` |
| [ ] | CRITICAL | BG(Database Migration V302) | `SignalDatabase.kt` | V302 마이그레이션 후 기존 메시지가 누락 없이 새 테이블 구조로 이전되는지 확인 | `V302_AddDeletedByColumn.kt` |
| [ ] | HIGH | BG(Message Deletion / Database Maintenance) | `AdminDeleteSendJob.kt` | 관리자 삭제 시 펜딩/실패/완료 상태가 DB에 기록되고 UI에 반영되는지 확인 | `MessageTable.kt` |
| [ ] | HIGH | BG(Database Migration V304) | `SignalDatabase.kt` | 수신자 테이블에 call/reply 알림 설정 컬럼 추가 및 기본값(0) 할당 확인 | `V304_CallAndReplyNotificationSettings.kt` |
| [ ] | HIGH | BG(Incoming Message Receiving) | `IncomingMessageObserver.kt` | 다수 메시지 동시 수신 시 일괄 처리 및 오류 발생 시 개별 처리 폴백 확인 | `IncomingMessageObserver.kt` |
| [ ] | HIGH | BG(Admin Message Deletion) | `AdminDeleteSendJob.kt` | 관리자 삭제 요청 시 신원 불일치 참여자 트래킹 및 네트워크 실패 수신자 관리 확인 | `AdminDeleteSendJob.kt` |
| [ ] | MEDIUM | BG(Database Query) | `RecipientTable.kt` | DB 쿼리 시 새로 추가된 알림 설정 필드들이 RecipientRecord 객체에 정상 매핑되는지 확인 | `RecipientTableCursorUtil.kt` |
| [ ] | MEDIUM | BG(Key Transparency Check) | `CheckKeyTransparencyJob.kt` | 키 투명성 검증 실패 시 간소화된 에러 전파 및 호출부 예외 처리 확인 | `KeyTransparencyApi.kt` |
| [ ] | MEDIUM | BG(Key Transparency Periodic Check) | `CheckKeyTransparencyJob.kt` | KT 검증 실패 시 재시도 예약 및 2차 실패 시 알림 시트 노출 확인 | `CheckKeyTransparencyJob.kt` |
| [ ] | MEDIUM | BG(BackupMessagesJob) | `BackupMessagesJob.kt` | ACI/E164 정보가 없는 저자의 메시지 필터링 및 백업 로그 기록 확인 | `ChatItemArchiveExporter.kt` |
| [ ] | LOW | BG(Database Transaction) | `SignalDatabase.kt` | tryRunInTransaction 수행 후 성공 시 true, 실패 롤백 시 false 반환 확인 | `SignalDatabase.kt` |
| [ ] | LOW | BG(Megaphones) | `Megaphones.java` | DB 쿼리를 통한 총 미디어 용량 계산값이 실제 파일 크기 합계와 근사한지 확인 | `AttachmentTable.kt` |
| [ ] | LOW | BG(Group Message Sending) | `AdminDeleteSendJob.kt` | 그룹 전송 완료 후 안전 번호 변경으로 인한 실패 건이 SendResult에 포함되는지 확인 | `GroupSendJobHelper.java` |
| [ ] | LOW | BG(Media Optimization) | `OptimizeMediaJob.kt` | 백업 구독 취소 예정 상태일 때 미디어 최적화 작업 건너뛰기 여부 확인 | `OptimizeMediaJob.kt` |
| [ ] | LOW | BG(Attachment Backup Upload) | `UploadAttachmentToArchiveJob.kt` | 유효하지 않은 첨부파일 백업 시 PERMANENT_FAILURE 상태가 DB에 기록되는지 확인 | `UploadAttachmentToArchiveJob.kt` |
| [ ] | LOW | BG(Megaphone Scheduling) | `Megaphones.java` | 백업 업셀 메가폰 노출 후 60일 이내 중복 노출 방지 스케줄링 확인 | `BackupUpsellSchedule.kt` |
| [ ] | LOW | BG(Incoming Message Batching) | `IncomingMessageObserver.kt` | 메시지 수신 시 대화방 업데이트와 전송 로그 삭제가 단일 트랜잭션으로 처리되는지 확인 | `BatchCache.kt` |
| [ ] | LOW | BG(Multi-device Sync) | `IncomingMessageObserver.kt` | 다른 기기에서 삭제된 메시지에 대한 고정(Pin) 동기화 요청 무시 확인 | `SyncMessageProcessor.kt` |
| [ ] | LOW | BG(Legacy Database Migration) | `LegacyMigrationJob.java` | 레거시 마이그레이션 중 시스템 연락처 색상 업데이트 비활성화 및 안정성 확인 | `LegacyMigrationJob.java` |
| [ ] | LOW | BG(Safety Number Verification) | `VerifySafetyNumberViewModel.kt` | KT 데이터 오염 시 CorruptedFailure 결과가 올바르게 반환되는지 확인 | `VerifySafetyNumberRepository.kt` |
| [ ] | LOW | BG(Storage Sync) | `StorageSyncJob.java` | 한 기기에서 변경한 멘션 알림 설정이 다른 기기로 동기화되는지 확인 | `StorageSyncModels.kt` |

### UI / Conversation

| 확인 | 위험도 | 트리거 | 진입점 | 테스트 시나리오 | 대상 파일 |
|------|--------|--------|--------|----------------|-----------|
| [ ] | HIGH | UI(Safety Number Change Bottom Sheet > Accept/Resend) | `SafetyNumberBottomSheetFragment.kt` | 안전 번호 변경으로 실패한 관리자 삭제 요청 승인 후 재전송 확인 | `SafetyNumberChangeRepository.java` |
| [ ] | HIGH | UI(Conversation List > Delete) | `ConversationListFragment.java` | 대화방 삭제 시 최적화된 트랜잭션 로직을 통해 DB 데이터가 완전히 정리되는지 확인 | `ThreadTable.kt` |
| [ ] | HIGH | UI(Conversation > Delete For Everyone) | `ConversationFragment.kt` | 관리자 삭제 실패 메시지에 대한 특정 수신자 대상 재전송 작업 등록 확인 | `MessageSender.java` |
| [ ] | MEDIUM | UI(Conversation > Message Interaction) | `ConversationFragment.kt` | 관리자 삭제 실패 메시지 클릭 시 신원 불일치 여부에 따른 안내 다이얼로그 노출 확인 | `ConversationFragment.kt` |
| [ ] | MEDIUM | UI(Conversation List > Megaphone Display) | `ConversationListFragment.java` | 메시지 수, 미디어 용량, 저장공간 부족 등 상황별 백업 권장 메가폰 노출 확인 | `Megaphones.java` |
| [ ] | MEDIUM | UI(Conversation > Safety Number Change Click) | `ConversationFragment.kt` | 발신/수신 메시지 케이스에 따라 적절한 안전 번호 변경 바텀 시트 팝업 확인 | `SafetyNumberBottomSheet.kt` |
| [ ] | MEDIUM | UI(Conversation > Message Options) | `ConversationFragment.kt` | 관리자 삭제 재전송 시 '이미 삭제됨' 상태 메시지에 대한 유효성 검사 예외 확인 | `MessageConstraintsUtil.kt` |
| [ ] | LOW | UI(Conversation > Message Item Update) | `ConversationFragment.kt` | 관리자 삭제 실패(전체/일부) 시 전용 에러 메시지 및 펜딩 상태 아이콘 확인 | `ConversationItemFooter.java` |
| [ ] | LOW | UI(Global > View Rendering) | `EmojiTextView.java` | RTL 환경에서 EmojiTextView의 텍스트 방향성이 명시적으로 설정되는지 확인 | `EmojiTextView.java` |
| [ ] | LOW | UI(Conversation > Message Item Rendering) | `ConversationFragment.kt` | 자신이 삭제한 메시지(1인칭)와 관리자가 삭제한 메시지의 텍스트 렌더링 확인 | `ConversationItem.java` |
| [ ] | LOW | UI(Conversation > Options Menu) | `ConversationFragment.kt` | 대화방 옵션 메뉴에서 '그룹 구성원' 보기 항목 제거 여부 확인 | `ConversationOptionsMenu.kt` |
| [ ] | LOW | UI(Conversation > Message Status Click) | `ConversationFragment.kt` | 메시지 삭제 실패 다이얼로그에서 '보내기' 클릭 시 삭제 명령 재전송 확인 | `ConversationDialogs.kt` |
| [ ] | LOW | UI(Conversation List > Long Press > Unarchive) | `ConversationListFragment.java` | 보관된 대화방의 '보관 취소' 액션 실행 시 전체 목록으로 정상 이동 확인 | `ConversationListFragment.java` |
| [ ] | LOW | UI(Message Details > Error Click) | `MessageDetailsFragment.kt` | 메시지 상세 화면의 전송 실패 아이콘 클릭 시 안전 번호 확인 시트 팝업 확인 | `MessageDetailsFragment.kt` |
| [ ] | LOW | UI(Stories...) | N/A | 스토리 관련 화면에서 전송 실패 시 안전 번호 확인 다이얼로그 정상 팝업 확인 | `StoriesLandingFragment.kt` |
| [ ] | LOW | UI(Conversation > Message List Rendering) | `ConversationFragment.kt` | 수신 멀티미디어 메시지의 지표 아이콘(답장/전달) 위치 및 크기 조정 확인 | `conversation_item_received_multimedia.xml` |
| [ ] | LOW | UI(Conversation > Quote Rendering) | `ConversationItem.java` | 라이트 모드/배경 적용 시 수신 메시지 인용구 라벨 배경색 가독성 확인 | `light_colors.xml` |
| [ ] | LOW | UI(Conversation > Mute Options) | `MuteDialog.java` | 무음 설정 다이얼로그의 시간 옵션 아이콘에 테마 틴트 적용 여부 확인 | `mute_dialog_item.xml` |

### UI / Settings

| 확인 | 위험도 | 트리거 | 진입점 | 테스트 시나리오 | 대상 파일 |
|------|--------|--------|--------|----------------|-----------|
| [ ] | MEDIUM | UI(Conversation Settings > Sounds and notifications / Group Invite) | `ConversationSettingsFragment.kt` | 내부 사용자 전용 알림 설정(V2) 진입 및 그룹 초대 성공 다이얼로그 노출 확인 | `ConversationSettingsFragment.kt` |
| [ ] | MEDIUM | UI(Member Label Settings > Save) | `MemberLabelFragment.kt` | 멤버 라벨 저장 시 '소개 글 대체' 안내 노출 및 로딩/에러 핸들링 확인 | `MemberLabelFragment.kt` |
| [ ] | MEDIUM | BG(Member Label Data Operations) | `MemberLabelViewModel.kt` | 라벨 저장 성공/실패 결과 전파 및 '다시 보지 않기' 설정 유지 확인 | `MemberLabelRepository.kt` |
| [ ] | MEDIUM | UI(Member Label Settings > Save/Edit) | `MemberLabelFragment.kt` | 멤버 라벨 글자 수 제한(24자) 및 소개 글 존재 시 안내 시트 제어 로직 확인 | `MemberLabelViewModel.kt` |
| [ ] | MEDIUM | UI(Group Invite > Success) | `GroupInviteSentDialog.java` | 다수 멤버 초대 시 결과 다이얼로그 팝업 및 참여 예정자 목록 노출 확인 | `GroupInviteSentDialog.java` |
| [ ] | MEDIUM | UI(Conversation Banner > GV1 Suggestion Click) | `ConversationFragment.kt` | GV1 마이그레이션 배너의 '멤버 추가' 클릭 시 제안 다이얼로그 정상 노출 확인 | `GroupsV1MigrationSuggestionsDialog.java` |
| [ ] | LOW | UI(Settings > Backups) | `BackupsSettingsViewModel.kt` | 구독 결제 대기(Pending) 상태가 백업 설정 화면에 올바르게 표시되는지 확인 | `BackupStateObserver.kt` |
| [ ] | LOW | UI(Settings > Local Backups) | `LocalBackupsFragment.kt` | 로컬 백업 업그레이드 시 로딩 표시 및 경로 URI 대신 사용자 경로 표시 확인 | `LocalBackupsFragment.kt` |
| [ ] | LOW | UI(Internal Settings > Disable internal user flag) | `InternalSettingsFragment.kt` | 내부 사용자 플래그 비활성화 시 디버그 로그 등 전용 기능 제한 확인 | `InternalSettingsFragment.kt` |
| [ ] | LOW | UI(Conversation Settings > View) | `ConversationSettingsFragment.kt` | 그룹 설정 진입 시 본인의 멤버 라벨 설정 권한(isGroupAdmin) 판단 확인 | `ConversationSettingsViewModel.kt` |
| [ ] | LOW | UI(Conversation Settings > Recipient Info) | `ConversationSettingsFragment.kt` | 프로필 영역에서 멤버 라벨(관리자 등) 표시 및 업데이트 시 재렌더링 확인 | `RecipientPreference.kt` |
| [ ] | LOW | UI(Sounds and Notifications Settings V2) | `SoundsAndNotificationsSettingsFragment2.kt` | Compose 기반 알림 설정 화면(V2) 진입 및 무음/전화/답장 옵션 변경 확인 | `SoundsAndNotificationsSettingsFragment2.kt` |
| [ ] | LOW | UI(Member Label Settings > Save) | `MemberLabelFragment.kt` | 멤버 라벨 설정 시 '소개' 대체 안내 바텀 시트의 응답 결과 전달 확인 | `MemberLabelAboutOverrideSheet.kt` |
| [ ] | LOW | UI(Global > Member Label Rendering) | `MemberLabelPillView.kt` | 멤버 라벨 표시 시 Bidi 격리 처리 및 다중 행 표시 시 둥근 모서리 변화 확인 | `MemberLabelPillView.kt` |
| [ ] | LOW | UI(Group Settings > View Members) | `GroupMemberListView.java` | 그룹 멤버 목록에서 멤버 라벨(Pill) 렌더링 및 소개 텍스트 숨김 처리 확인 | `GroupMemberListAdapter.java` |
| [ ] | LOW | UI(Create Group > Create Success) | `AddGroupDetailsActivity.java` | 그룹 생성 후 초대 발송 다이얼로그 노출 및 Dismiss 시 대화방 이동 확인 | `AddGroupDetailsActivity.java` |
| [ ] | LOW | UI(Profile > View Info) | `AboutSheet.kt` | 사용자 프로필 '소개' 시트의 멤버 라벨에 RTL 텍스트 방향성 적용 확인 | `AboutSheet.kt` |
| [ ] | LOW | UI(Conversation > Member Avatar/Name Click) | `RecipientBottomSheetDialogFragment.kt` | 긴 멤버 라벨이 설정된 경우 바텀 시트에서 줄바꿈되어 전체 내용 노출 확인 | `RecipientBottomSheetDialogFragment.kt` |
| [ ] | LOW | UI(Global > Loading State) | `LocalBackupsFragment.kt` | 작업 속도에 따른 로딩 다이얼로그 지연 노출 및 최소 유지 시간 로직 확인 | `Dialogs.kt` |
| [ ] | LOW | UI(Global > Path Display) | `LocalBackupsFragment.kt` | 구버전 안드로이드 기기에서 백업 경로 표시 시 크래시 방지 및 정상 노출 확인 | `StorageUtil.java` |

### WebRTC / Call

| 확인 | 위험도 | 트리거 | 진입점 | 테스트 시나리오 | 대상 파일 |
|------|--------|--------|--------|----------------|-----------|
| [ ] | HIGH | BG(Message/Call Notification) | `DefaultMessageNotifier.kt` | 무음 대화방에서도 멘션/답장/부재중 전화 시 예외 알림 발생 확인 | `NotificationStateProvider.kt` |
| [ ] | MEDIUM | UI(Call > Info > Participant Click) | `CallScreen.kt` | 내부 사용자 설정 시 통화 참여자 클릭하여 액션 시트(음소거/제거) 노출 확인 | `CallInfoView.kt` |
| [ ] | MEDIUM | UI(Call > Info > Participant Action) | `CallScreen.kt` | 참여자 음소거/제거 클릭 시 서버 요청 전달 및 확인 다이얼로그 노출 확인 | `CallInfoCallbacks.kt` |
| [ ] | MEDIUM | UI(Call > Participant Video > Long Press) | `CallScreen.kt` | 내부 사용자 설정 시 참여자 영상 길게 눌러 관리자용 컨텍스트 메뉴 노출 확인 | `CallScreen.kt` |
| [ ] | MEDIUM | BG(Incoming Call Notification) | `IncomingCallActionProcessor.java` | 수신자 무음 및 시스템 DND 상태에 따른 통화 알림 차단/허용 정책 확인 | `DoNotDisturbUtil.java` |
| [ ] | MEDIUM | BG(WebRTC Call Setup) | `WebRtcActionProcessor.java` | DND/알림 없음 설정 시 통화 연결 중(Connecting) 알림 노출 차단 확인 | `BeginCallActionProcessorDelegate.java` |
| [ ] | MEDIUM | BG(Incoming Call Processing) | `WebRtcActionProcessor.java` | 알림 거부 수신자로부터의 전화 수신 시 벨소리/화면 켜짐 조기 차단 확인 | `IncomingCallActionProcessor.java` |
| [ ] | MEDIUM | BG(Incoming Group Call Processing) | `WebRtcActionProcessor.java` | 그룹 알림 해제 시 그룹 통화 벨소리 및 화면 표시 중단 여부 확인 | `IncomingGroupCallActionProcessor.java` |
| [ ] | MEDIUM | BG(WebRTC Participant Action) | `WebRtcActionProcessor.java` | 그룹 통화 중 관리자의 원격 음소거(Remote Mute) 요청 처리 확인 | `GroupConnectedActionProcessor.java` |
| [ ] | MEDIUM | UI(Call > Camera Toggle) | `WebRtcCallActivity.java` | 카메라 활성화 시 초기화 레이스 컨디션 방지 및 초기 상태 반영 확인 | `Camera.java` |
| [ ] | LOW | UI(Call > Participant Pager > Long Press) | `CallScreen.kt` | 통화 페이저 영상 길게 눌러 액션 시트 팝업 및 짧게 탭하여 UI 토글 확인 | `CallParticipantsPager.kt` |
| [ ] | LOW | UI(Call > Mediator Render) | `WebRtcCallActivity.java` | Mediator를 통한 관리자 권한 및 내부 사용자 정보의 CallScreen 전달 확인 | `ComposeCallScreenMediator.kt` |
| [ ] | LOW | BG(WebRtc Service Control) | `SignalCallManager.java` | sendRemoteMuteRequest 호출 시 ActionProcessor로 정상 전달 확인 | `SignalCallManager.java` |
| [ ] | LOW | BG(WebRtc Action Handling) | `WebRtcActionProcessor.java` | 지원하지 않는 Processor에서 원격 음소거 요청 시 로그 기록 확인 | `WebRtcActionProcessor.java` |

### Registration / Restore

| 확인 | 위험도 | 트리거 | 진입점 | 테스트 시나리오 | 대상 파일 |
|------|--------|--------|--------|----------------|-----------|
| [ ] | MEDIUM | UI(Registration/Restore > Enter Backup Key) | `EnterBackupKeyFragment.kt` | 30자리 백업 키 입력 시 실제 백업 메타데이터와의 실시간 유효성 검증 확인 | `EnterBackupKeyViewModel.kt` |
| [ ] | MEDIUM | UI(Registration/Restore > Restore Local Backup Failure) | `RestoreLocalBackupActivity.kt` | 복구 실패 시 에러 다이얼로그 및 고객 지원 문의 연동 기능 확인 | `RestoreLocalBackupActivity.kt` |
| [ ] | MEDIUM | UI(Registration/Restore > Select Restore Method) | `RestoreActivity.kt` | 기기 환경에 따른 로컬 백업 V1/V2 복구 방식 분기 제안 확인 | `RestoreViewModel.kt` |
| [ ] | MEDIUM | UI(Registration/Restore > Local Backup V2 Flow) | `PostRegistrationRestoreLocalBackupFragment.kt` | 가입 후 단계에서 로컬 백업 V2 복구 워크플로우 및 키 검증 확인 | `PostRegistrationRestoreLocalBackupFragment.kt` |
| [ ] | LOW | UI(New Device Transfer > Success) | `NewDeviceTransferFragment.kt` | 기기 이전 성공 후 사용자 이름 복구 필요 플래그 저장 및 Job 등록 확인 | `NewDeviceTransferViewModel.kt` |
| [ ] | LOW | BG(Restore State Management) | `RestoreLocalBackupActivity.kt` | 복구 실패 후 복구 결정 상태를 START로 초기화하는 로직 확인 | `RestoreLocalBackupActivityViewModel.kt` |
| [ ] | LOW | UI(Restore Local Backup > Success) | `RestoreLocalBackupFragment.kt` | 가입 전 로컬 백업 복구 성공 시 사용자 이름 복구 필요 플래그 저장 확인 | `RestoreLocalBackupViewModel.kt` |
| [ ] | LOW | UI(Registration/Restore > Select Method Click) | `SelectRestoreMethodFragment.kt` | 복구 선택 화면에서 V2 방식 선택 시 대응하는 프래그먼트 이동 확인 | `SelectRestoreMethodFragment.kt` |