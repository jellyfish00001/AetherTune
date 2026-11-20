/**
 * SpeechWorkspace 凍結旗標（2026-11-20 14:05 Q5，Asia/Taipei）。
 *
 * 凍結期間只隱藏 Manual TTS／語音重建的 Mode 入口；
 * SpeechWorkspace 元件、路由與後端都保留，不刪程式。
 * 不影響即時 VC／F08 UI，也不改裝置清單資料層
 * （`getAudioDevices`／`app/src/services/speech.ts` 的 `audio_devices`）。
 *
 * 預設隱藏：SPEECH_WORKSPACE_FROZEN_DEFAULT = true
 *
 * 開發者暫時解除（擇一，重新載入 App 後生效）：
 * - 開發者工具：localStorage.setItem('aethertune.speech-workspace.unfreeze', '1')
 * - 將本檔 SPEECH_WORKSPACE_FROZEN_DEFAULT 改為 false
 *
 * 永久還原入口顯示：git revert 實作此隱藏的 commit（詳見 docs/specs/tts-freeze-split-plan.md「入口隱藏與退回」）。
 * 關閉暫時解除：localStorage.removeItem('aethertune.speech-workspace.unfreeze')
 */
export const SPEECH_WORKSPACE_FROZEN_DEFAULT = true;
export const SPEECH_WORKSPACE_UNFREEZE_STORAGE_KEY = 'aethertune.speech-workspace.unfreeze';

export const TTS_WORKSPACE_MODES = ['speech_reconstruction', 'text_to_speech'] as const;

function storageUnfreeze(): boolean {
  try {
    const value = window.localStorage.getItem(SPEECH_WORKSPACE_UNFREEZE_STORAGE_KEY);
    return value === '1' || value === 'true';
  } catch {
    // Native WebView storage 可能不可用；此時只看編譯期旗標。
    return false;
  }
}

/** 凍結為 true 時，UI 不得顯示 SpeechWorkspace 入口，也不得切進 TTS 模式。 */
export function isSpeechWorkspaceFrozen(): boolean {
  if (!SPEECH_WORKSPACE_FROZEN_DEFAULT) return false;
  if (storageUnfreeze()) return false;
  return true;
}

export function isTtsWorkspaceMode(mode: string): boolean {
  return (TTS_WORKSPACE_MODES as readonly string[]).includes(mode);
}
