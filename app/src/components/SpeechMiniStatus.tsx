import React, { useEffect, useState } from 'react';
import { getSpeechStatus, type SpeechSnapshot } from '../services/speech';
import { LoadStatus } from './LoadStatus';

// Mini 收起 Quick Input 時仍讀取正式 snapshot，避免只剩 TTS 字樣而看不到等待。
export function SpeechMiniStatus({ engine }: { engine: string }) {
  const [snapshot, setSnapshot] = useState<SpeechSnapshot>();
  useEffect(() => {
    let mounted = true;
    const refresh = () => { void getSpeechStatus().then(next => { if (mounted) setSnapshot(next); }).catch(() => {}); };
    refresh();
    const timer = setInterval(refresh, 1000);
    return () => { mounted = false; clearInterval(timer); };
  }, []);
  return <LoadStatus engine={engine} progress={snapshot?.progress ?? undefined} active={!!snapshot?.current_request_id} minimal/>;
}
