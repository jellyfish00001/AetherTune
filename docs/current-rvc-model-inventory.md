# 目前 RVC 模型清單

盤點時間：2026-09-20（Asia/Taipei）

以下檔案目前存在於工作區，並依 basename 找到同名 `.pth`／`.index` 配對。現在已將四組檔案登錄為 `candidate`；這只證明檔案配對與 hash，來源、取樣率、f0、RVC revision、dataset batch、授權與實際音質仍是 `WAITING`，不能直接標成 `ready`。

| model id | weights | weights SHA-256 | index | index SHA-256 | status |
|---|---:|---|---:|---|---|
| `Chinese_Narrator_Uncle` | 55,227,861 bytes | `B3D2C8B5B44BC3ACDD667D2A49D62C94FA467FE22B7E5AC9D5A9AC93580FF25F` | 27,159,579 bytes | `A430884317C974CE04AE9D50136630BFAFBA3408CEF5CD7528BDC51D9555BED5` | candidate / metadata waiting |
| `Kafka_CN_Yujie` | 55,232,064 bytes | `143E3E4CDE43CDEF4A4B3EACAB84DB63580C57AC68140D4B4A5A6129539A7F7D` | 118,552,419 bytes | `B9374E0DB11C2EF8C8A318E97734BA0C99FD03B00AD0FF078F18863A7A6D569C` | candidate / metadata waiting |
| `Sage_CN_HeroicFemale` | 57,581,999 bytes | `57C2A770211A7F08C7AE973E6343006547CA4400752CE4DA17842117E1E556AD` | 18,624,899 bytes | `4D9DDA9D71D9BB6A65283718F0390AA45951A818E69F57B8686583AC31BB9AF9` | candidate / metadata waiting |
| `Wukong_HeroicMale` | 55,225,095 bytes | `40C9284592DF6BE72ADA52BEB9032EEFE8C29C43E7EBB00834F9993C7CA4F453` | 5,959,939 bytes | `745D1852A3888CEA462ABE6DB3C2FF4A66E95FFFD65FD0EDB6BF83ACDB45CF37` | candidate / metadata waiting |

## 下一步

逐組確認來源與授權、取樣率、f0 method、RVC version、dataset batch、訓練或下載 revision，再把 `unknown` 欄位替換成實際值。完成前不要直接把這些檔案標成 `ready` 或投入公開通話。
