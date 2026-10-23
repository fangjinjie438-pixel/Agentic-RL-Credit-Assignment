# S2 人工审阅材料（尚未签核）

数据 revision：`s2-ee9902b8fc67ad1b39533598`。
本文件包含私有约束、完整合法解和原始证据，仅供数据审核。不要发送给执行教师或学生策略。
尚未进行人工/独立模型审核，也未批准正式训练数据。空白表单不是通过记录。

本包覆盖 dev, train；可审 7 条，PLAN 的 200 条人工抽检仍差 193 条。数量不足不能通过复制记录补齐。

## 如何完成真实签核

1. 逐条核对下面原字段/原句、数值与单位、所有合法商品，以及隐藏约束是否在正确渠道出现。
2. 对照同 root 的反事实，只允许一个约束值改变，并确认合法解非空且要求决策改变。
3. 检查任务是否符合办公电子设备采购、表达是否自然、是否具备有意义的检索与核验难度；泛泛的品类或浅层模板可拒收。
4. 检查品牌/型号/家族保守聚类。若家族错误，先修来源和重建新 revision，再重新签核；不要只改审核表。
5. 实际完成后复制 `reviews-template.json` 为新文件，填写真实 reviewer、带时区 reviewed_at、accept/reject 和具体 notes。未审核项应删除或保持空白；空白项不能通过审计。
6. 模型分歧必须由实际人工裁决，并仅在已完成裁决时填 `adjudicates_model_disagreement=true`。拒收任务仍在数据包内时发布保持 withheld。

独立模型输入位于 `independent-inputs.jsonl`，只是尚未执行的审阅输入。记录实际模型标识/revision、日期、提示版本、原始响应与来源；不得把本脚本或词面检查称为独立模型。

## 商品事实与来源

### B01FB654PI · NETGEAR AC1600 WiFi VDSL/ADSL Modem Router – 802.11ac Dual Band Gigabit (D6400-100NAS)

split=`train`；family=`brand:netgear`；brand=`NETGEAR`；model=`D6400-100NAS`。

商品哈希：`485235f10e502d42fe3dd31d3c34ba51dbbe0087aa75e890ad7754a0cecdd3fb`。

- `B01FB654PI:details:price`：price = 130；原句 "130.0"；原字段 `["price"]`；原行 `869`；原单位 `USD` → `USD`；原记录 SHA `46c4fcf5a5e60cdb2ee20f3ccc2a5fd3e31a8d24fa90a802a67718dbd716060a`。
- `B01FB654PI:details:weight_g`：weight_g = 421.8409041；原句 "14.88 Ounces"；原字段 `["details", "Item Weight"]`；原行 `869`；原单位 `Ounces` → `g`；原记录 SHA `46c4fcf5a5e60cdb2ee20f3ccc2a5fd3e31a8d24fa90a802a67718dbd716060a`。
- `B01FB654PI:details:connectivity`：connectivity = "Wi Fi"；原句 "Wi Fi"；原字段 `["details", "Connectivity Technology"]`；原行 `869`；原单位 `None` → `None`；原记录 SHA `46c4fcf5a5e60cdb2ee20f3ccc2a5fd3e31a8d24fa90a802a67718dbd716060a`。

### B09H2JQD48 · KECOP Baby Pink USB Wire Keyboard with Rainbow LED Backlight Full 104 Keys Water-Resistant Mechanical Feeling Game Keyboard for Desktop, Computer, PC (Baby Pink)

split=`train`；family=`brand:kecop`；brand=`KECOP`；model=`None`。

商品哈希：`2061e5a27ffbdd1512e44fa17979cee887635aa64388b840e39f655de5cadd99`。

- `B09H2JQD48:details:price`：price = 23.99；原句 "23.99"；原字段 `["price"]`；原行 `176`；原单位 `USD` → `USD`；原记录 SHA `900cb12381dfa5a68aff04f8ede75ef4df5ee242ddaa6a5ed6c9768f4bdbe974`。
- `B09H2JQD48:details:weight_g`：weight_g = 453.59237；原句 "1 pounds"；原字段 `["details", "Item Weight"]`；原行 `176`；原单位 `pounds` → `g`；原记录 SHA `900cb12381dfa5a68aff04f8ede75ef4df5ee242ddaa6a5ed6c9768f4bdbe974`。
- `B09H2JQD48:details:color`：color = "Baby Pink"；原句 "Baby Pink"；原字段 `["details", "Color"]`；原行 `176`；原单位 `None` → `None`；原记录 SHA `900cb12381dfa5a68aff04f8ede75ef4df5ee242ddaa6a5ed6c9768f4bdbe974`。
- `B09H2JQD48:details:connectivity`：connectivity = "USB"；原句 "USB"；原字段 `["details", "Connectivity Technology"]`；原行 `176`；原单位 `None` → `None`；原记录 SHA `900cb12381dfa5a68aff04f8ede75ef4df5ee242ddaa6a5ed6c9768f4bdbe974`。
- `B09H2JQD48:details:operating_system`：operating_system = "Linux, Windows Vista, Windows XP, Windows 8, Windows 7, Windows 10"；原句 "Linux, Windows Vista, Windows XP, Windows 8, Windows 7, Windows 10"；原字段 `["details", "Operating System"]`；原行 `176`；原单位 `None` → `None`；原记录 SHA `900cb12381dfa5a68aff04f8ede75ef4df5ee242ddaa6a5ed6c9768f4bdbe974`。

### B09X983942 · Macally 2.4G USB Wireless Keyboard for Laptop or Computer - Keep it Simple - Full Size Keyboard with Numeric Keypad & 13 Shortcut Keys - Plug and Play PC Keyboard Wireless - White Keyboard Cordless

split=`train`；family=`brand:macally`；brand=`Macally`；model=`None`。

商品哈希：`639746191de24da2b24bdae19d4add4ceb1649255868b7297c0649061c968233`。

- `B09X983942:details:price`：price = 19.99；原句 "19.99"；原字段 `["price"]`；原行 `182`；原单位 `USD` → `USD`；原记录 SHA `66fd7e2ef6634b7de2b4850a3b1d4b11f51b76882a590f9a65f78a15bc774160`。
- `B09X983942:details:weight_g`：weight_g = 616.8856232；原句 "1.36 pounds"；原字段 `["details", "Item Weight"]`；原行 `182`；原单位 `pounds` → `g`；原记录 SHA `66fd7e2ef6634b7de2b4850a3b1d4b11f51b76882a590f9a65f78a15bc774160`。
- `B09X983942:details:color`：color = "White"；原句 "White"；原字段 `["details", "Color"]`；原行 `182`；原单位 `None` → `None`；原记录 SHA `66fd7e2ef6634b7de2b4850a3b1d4b11f51b76882a590f9a65f78a15bc774160`。
- `B09X983942:details:connectivity`：connectivity = "RF, USB"；原句 "RF, USB"；原字段 `["details", "Connectivity Technology"]`；原行 `182`；原单位 `None` → `None`；原记录 SHA `66fd7e2ef6634b7de2b4850a3b1d4b11f51b76882a590f9a65f78a15bc774160`。
- `B09X983942:details:operating_system`：operating_system = "Windows 7"；原句 "Windows 7"；原字段 `["details", "Operating System"]`；原行 `182`；原单位 `None` → `None`；原记录 SHA `66fd7e2ef6634b7de2b4850a3b1d4b11f51b76882a590f9a65f78a15bc774160`。

### B0B5LDPJLD · Mini Bluetooth Keyboard Wireless Keyboard - Ultra-Slim, Silent, Multi-Device, Illuminated, 7 Colors RGB, for Apple iPad iPhone Samsung Tablet Phone Smartphone iOS Android Windows

split=`train`；family=`brand:runelves`；brand=`RunElves`；model=`RE-20220702`。

商品哈希：`30aa20b5c1fd238b0c2cb5e2877403019d51067ebf9189ef22b488f258511d16`。

- `B0B5LDPJLD:details:price`：price = 39.99；原句 "39.99"；原字段 `["price"]`；原行 `808`；原单位 `USD` → `USD`；原记录 SHA `e1c82179b3ca70cf9bea88002f3e9440ca52460ac2da08a8ff564414e91ed756`。
- `B0B5LDPJLD:details:weight_g`：weight_g = 240.9709465625；原句 "8.5 ounces"；原字段 `["details", "Item Weight"]`；原行 `808`；原单位 `ounces` → `g`；原记录 SHA `e1c82179b3ca70cf9bea88002f3e9440ca52460ac2da08a8ff564414e91ed756`。
- `B0B5LDPJLD:details:color`：color = "Pink"；原句 "Pink"；原字段 `["details", "Color"]`；原行 `808`；原单位 `None` → `None`；原记录 SHA `e1c82179b3ca70cf9bea88002f3e9440ca52460ac2da08a8ff564414e91ed756`。
- `B0B5LDPJLD:details:connectivity`：connectivity = "Bluetooth"；原句 "Bluetooth"；原字段 `["details", "Connectivity Technology"]`；原行 `808`；原单位 `None` → `None`；原记录 SHA `e1c82179b3ca70cf9bea88002f3e9440ca52460ac2da08a8ff564414e91ed756`。
- `B0B5LDPJLD:details:operating_system`：operating_system = "Windows/Android/Linux/iOS"；原句 "Windows/Android/Linux/iOS"；原字段 `["details", "Operating System"]`；原行 `808`；原单位 `None` → `None`；原记录 SHA `e1c82179b3ca70cf9bea88002f3e9440ca52460ac2da08a8ff564414e91ed756`。

### B0B97BKQJV · Thinlerain 15 inch PC Monitor Desktop Monitor with 1440×900, Small Monitor with 16:10 LED Monitor, TFT Panel, 60 Hz, 5Ms, VGA, HDMI, Built-in Speakers

split=`dev`；family=`brand:thinlerain`；brand=`Thinlerain`；model=`None`。

商品哈希：`d96dbbfd8bd2ca5e10c92a5b0cd58bdf8e6f71cbb3ba36dd1fa7ca50b6dd604e`。

- `B0B97BKQJV:details:price`：price = 85.99；原句 "85.99"；原字段 `["price"]`；原行 `691`；原单位 `USD` → `USD`；原记录 SHA `8805b91d86779db64358b47576ff9dea981dfe8e9d95f8f8008585bba3961b1b`。
- `B0B97BKQJV:details:weight_g`：weight_g = 1514.9985158；原句 "3.34 pounds"；原字段 `["details", "Item Weight"]`；原行 `691`；原单位 `pounds` → `g`；原记录 SHA `8805b91d86779db64358b47576ff9dea981dfe8e9d95f8f8008585bba3961b1b`。
- `B0B97BKQJV:details:screen_size`：screen_size = "15 Inches"；原句 "15 Inches"；原字段 `["details", "Screen Size"]`；原行 `691`；原单位 `None` → `None`；原记录 SHA `8805b91d86779db64358b47576ff9dea981dfe8e9d95f8f8008585bba3961b1b`。
- `B0B97BKQJV:details:display_resolution`：display_resolution = "1440 x 900 Pixels"；原句 "1440 x 900 Pixels"；原字段 `["details", "Display Resolution Maximum"]`；原行 `691`；原单位 `None` → `None`；原记录 SHA `8805b91d86779db64358b47576ff9dea981dfe8e9d95f8f8008585bba3961b1b`。

### B0BKFX6FWW · mafiti RK101 Computer Keyboard Mouse Combo Wired, RGB Backlit USB Keyboard for PC Mac Laptop Desktop, Gaming Office

split=`train`；family=`brand:mafiti`；brand=`Mafiti`；model=`Mafiti RK101`。

商品哈希：`67bd99ea0e64c17c046ff7c52764e04590c32eb658e35c9388c8be76d3206eaa`。

- `B0BKFX6FWW:details:price`：price = 19.99；原句 "19.99"；原字段 `["price"]`；原行 `514`；原单位 `USD` → `USD`；原记录 SHA `7b810c3b957df44a3637736e3c86e8987d9d4c7e6a7e4418a56fcdba32c8a2bd`。
- `B0BKFX6FWW:details:weight_g`：weight_g = 748.4274105；原句 "1.65 pounds"；原字段 `["details", "Item Weight"]`；原行 `514`；原单位 `pounds` → `g`；原记录 SHA `7b810c3b957df44a3637736e3c86e8987d9d4c7e6a7e4418a56fcdba32c8a2bd`。
- `B0BKFX6FWW:details:connectivity`：connectivity = "Usb"；原句 "Usb"；原字段 `["details", "Connectivity Technology"]`；原行 `514`；原单位 `None` → `None`；原记录 SHA `7b810c3b957df44a3637736e3c86e8987d9d4c7e6a7e4418a56fcdba32c8a2bd`。

### B0BKS1K986 · LENTION USB C Docking Station, 10 Gbps USB C&USB A Ports, 4K 60Hz HDMI, 100W PD, Ethernet, Card Reader, USB 3.0, AUX, USB C Dock for MacBook/Surface, More, Stable Driver USB C Hub(CB-D65, Space Gray)

split=`train`；family=`brand:lention`；brand=`LENTION`；model=`None`。

商品哈希：`f67bd3268e2aabef1cd6ab53c8b6a7e1aa97f125540bec1cb52b4d66d6626349`。

- `B0BKS1K986:details:price`：price = 89.99；原句 "89.99"；原字段 `["price"]`；原行 `47`；原单位 `USD` → `USD`；原记录 SHA `07de1c15ac494f03c8265a1a8c87c1941acb0707864b1b99ec0a45fd243cd74b`。
- `B0BKS1K986:details:weight_g`：weight_g = 447.922465375；原句 "15.8 ounces"；原字段 `["details", "Item Weight"]`；原行 `47`；原单位 `ounces` → `g`；原记录 SHA `07de1c15ac494f03c8265a1a8c87c1941acb0707864b1b99ec0a45fd243cd74b`。
- `B0BKS1K986:details:color`：color = "Space Gray"；原句 "Space Gray"；原字段 `["details", "Color"]`；原行 `47`；原单位 `None` → `None`；原记录 SHA `07de1c15ac494f03c8265a1a8c87c1941acb0707864b1b99ec0a45fd243cd74b`。
- `B0BKS1K986:details:hardware_interface`：hardware_interface = "MicroSD, USB Type C, Ethernet, HDMI, USB 3.0, USB 3.2 Gen 2"；原句 "MicroSD, USB Type C, Ethernet, HDMI, USB 3.0, USB 3.2 Gen 2"；原字段 `["details", "Hardware Interface"]`；原行 `47`；原单位 `None` → `None`；原记录 SHA `07de1c15ac494f03c8265a1a8c87c1941acb0707864b1b99ec0a45fd243cd74b`。

### B0BWYJJLSF · Wireless Keyboard and Mouse Combo, EDJO Full-Sized Ergonomic Computer Keyboard with Wrist Rest and 3 Level DPI Adjustable Wireless Mouse for Windows, Mac OS Desktop/Laptop/PC (White)

split=`train`；family=`brand:edjo`；brand=`EDJO`；model=`None`。

商品哈希：`1276c7c571a175be1e8f056918903cb621246750d81535e82965ec58aa4860b9`。

- `B0BWYJJLSF:details:price`：price = 34.99；原句 "34.99"；原字段 `["price"]`；原行 `630`；原单位 `USD` → `USD`；原记录 SHA `dd0aa7b96c37769d1b03fbc4b86491b5256df185ad86ddc6e306b4f3114421af`。
- `B0BWYJJLSF:details:weight_g`：weight_g = 780.1788764；原句 "1.72 pounds"；原字段 `["details", "Item Weight"]`；原行 `630`；原单位 `pounds` → `g`；原记录 SHA `dd0aa7b96c37769d1b03fbc4b86491b5256df185ad86ddc6e306b4f3114421af`。
- `B0BWYJJLSF:details:color`：color = "White"；原句 "White"；原字段 `["details", "Color"]`；原行 `630`；原单位 `None` → `None`；原记录 SHA `dd0aa7b96c37769d1b03fbc4b86491b5256df185ad86ddc6e306b4f3114421af`。
- `B0BWYJJLSF:details:connectivity`：connectivity = "Usb, Radio Frequency"；原句 "Usb, Radio Frequency"；原字段 `["details", "Connectivity Technology"]`；原行 `630`；原单位 `None` → `None`；原记录 SHA `dd0aa7b96c37769d1b03fbc4b86491b5256df185ad86ddc6e306b4f3114421af`。

## 逐条任务核对

### task-72e45343984d6a3ce84c (base, train)

任务 SHA：`f66729755239401b791f992bd70d42d1a3d9e99d0ea22e7bd24c3549ded9aeda`；root：`task-72e45343984d6a3ce84c`。

Query: Please recommend one office electronic device. My required price in USD is at most 23.99.

Persona: My required color is exactly Baby Pink.

```json
{
  "clarifications": [
    {
      "question_id": "weight",
      "question": "What is your maximum device weight?",
      "answer": "My required weight in grams is at most 453.59237.",
      "constraint_ids": [
        "weight"
      ],
      "trigger_keywords": [
        "weight",
        "mass"
      ]
    }
  ],
  "constraints": [
    {
      "id": "budget",
      "source": "query",
      "field": "price",
      "op": "lte",
      "value": 23.99,
      "evidence_ids": [
        "B01FB654PI:details:price",
        "B09H2JQD48:details:price",
        "B09X983942:details:price",
        "B0B5LDPJLD:details:price",
        "B0BKFX6FWW:details:price",
        "B0BKS1K986:details:price",
        "B0BWYJJLSF:details:price"
      ]
    },
    {
      "id": "color",
      "source": "persona",
      "field": "color",
      "op": "eq",
      "value": "Baby Pink",
      "evidence_ids": [
        "B09H2JQD48:details:color",
        "B09X983942:details:color",
        "B0B5LDPJLD:details:color",
        "B0BKS1K986:details:color",
        "B0BWYJJLSF:details:color"
      ]
    },
    {
      "id": "weight",
      "source": "clarification",
      "field": "weight_g",
      "op": "lte",
      "value": 453.59237,
      "evidence_ids": [
        "B01FB654PI:details:weight_g",
        "B09H2JQD48:details:weight_g",
        "B09X983942:details:weight_g",
        "B0B5LDPJLD:details:weight_g",
        "B0BKFX6FWW:details:weight_g",
        "B0BKS1K986:details:weight_g",
        "B0BWYJJLSF:details:weight_g"
      ]
    }
  ],
  "feasible_product_ids": [
    "B09H2JQD48"
  ]
}
```

程序独立重算解集一致：`True`。这只是程序检查，不是人工通过。

同 root 任务：`task-72e45343984d6a3ce84c` (base)

待核对：原句/单位；完整合法解；隐藏渠道分离；家族身份；单约束反事实；表达保真与实际任务难度。

### task-964a2c1b4a9586d4b9ea (base, train)

任务 SHA：`f4ff13b89ad3a1d5e3e9700219509144b7927c4390caffae9d44fe7de92d493b`；root：`task-964a2c1b4a9586d4b9ea`。

Query: Please recommend one office electronic device. My required price in USD is at most 39.99.

Persona: My required color is exactly Pink.

```json
{
  "clarifications": [
    {
      "question_id": "weight",
      "question": "What is your maximum device weight?",
      "answer": "My required weight in grams is at most 240.9709465625.",
      "constraint_ids": [
        "weight"
      ],
      "trigger_keywords": [
        "weight",
        "mass"
      ]
    }
  ],
  "constraints": [
    {
      "id": "budget",
      "source": "query",
      "field": "price",
      "op": "lte",
      "value": 39.99,
      "evidence_ids": [
        "B01FB654PI:details:price",
        "B09H2JQD48:details:price",
        "B09X983942:details:price",
        "B0B5LDPJLD:details:price",
        "B0BKFX6FWW:details:price",
        "B0BKS1K986:details:price",
        "B0BWYJJLSF:details:price"
      ]
    },
    {
      "id": "color",
      "source": "persona",
      "field": "color",
      "op": "eq",
      "value": "Pink",
      "evidence_ids": [
        "B09H2JQD48:details:color",
        "B09X983942:details:color",
        "B0B5LDPJLD:details:color",
        "B0BKS1K986:details:color",
        "B0BWYJJLSF:details:color"
      ]
    },
    {
      "id": "weight",
      "source": "clarification",
      "field": "weight_g",
      "op": "lte",
      "value": 240.9709465625,
      "evidence_ids": [
        "B01FB654PI:details:weight_g",
        "B09H2JQD48:details:weight_g",
        "B09X983942:details:weight_g",
        "B0B5LDPJLD:details:weight_g",
        "B0BKFX6FWW:details:weight_g",
        "B0BKS1K986:details:weight_g",
        "B0BWYJJLSF:details:weight_g"
      ]
    }
  ],
  "feasible_product_ids": [
    "B0B5LDPJLD"
  ]
}
```

程序独立重算解集一致：`True`。这只是程序检查，不是人工通过。

同 root 任务：`task-964a2c1b4a9586d4b9ea` (base)

待核对：原句/单位；完整合法解；隐藏渠道分离；家族身份；单约束反事实；表达保真与实际任务难度。

### task-9e9c41995b5779485caa (base, train)

任务 SHA：`403694c105a4ba5b4b51c874b23139c5761be725969ecf5c472bc23de926650a`；root：`task-9e9c41995b5779485caa`。

Query: Please recommend one office electronic device. My required price in USD is at most 89.99.

Persona: My required color is exactly Space Gray.

```json
{
  "clarifications": [
    {
      "question_id": "weight",
      "question": "What is your maximum device weight?",
      "answer": "My required weight in grams is at most 447.922465375.",
      "constraint_ids": [
        "weight"
      ],
      "trigger_keywords": [
        "weight",
        "mass"
      ]
    }
  ],
  "constraints": [
    {
      "id": "budget",
      "source": "query",
      "field": "price",
      "op": "lte",
      "value": 89.99,
      "evidence_ids": [
        "B01FB654PI:details:price",
        "B09H2JQD48:details:price",
        "B09X983942:details:price",
        "B0B5LDPJLD:details:price",
        "B0BKFX6FWW:details:price",
        "B0BKS1K986:details:price",
        "B0BWYJJLSF:details:price"
      ]
    },
    {
      "id": "color",
      "source": "persona",
      "field": "color",
      "op": "eq",
      "value": "Space Gray",
      "evidence_ids": [
        "B09H2JQD48:details:color",
        "B09X983942:details:color",
        "B0B5LDPJLD:details:color",
        "B0BKS1K986:details:color",
        "B0BWYJJLSF:details:color"
      ]
    },
    {
      "id": "weight",
      "source": "clarification",
      "field": "weight_g",
      "op": "lte",
      "value": 447.922465375,
      "evidence_ids": [
        "B01FB654PI:details:weight_g",
        "B09H2JQD48:details:weight_g",
        "B09X983942:details:weight_g",
        "B0B5LDPJLD:details:weight_g",
        "B0BKFX6FWW:details:weight_g",
        "B0BKS1K986:details:weight_g",
        "B0BWYJJLSF:details:weight_g"
      ]
    }
  ],
  "feasible_product_ids": [
    "B0BKS1K986"
  ]
}
```

程序独立重算解集一致：`True`。这只是程序检查，不是人工通过。

同 root 任务：`task-9e9c41995b5779485caa` (base), `task-9e9c41995b5779485caa-cf-018340a0` (counterfactual)

待核对：原句/单位；完整合法解；隐藏渠道分离；家族身份；单约束反事实；表达保真与实际任务难度。

### task-9e9c41995b5779485caa-cf-018340a0 (counterfactual, train)

任务 SHA：`7109543f261f90a6716e28c1c558bc39cddd41bda7101ed60689171dd3a967ae`；root：`task-9e9c41995b5779485caa`。

Query: Please recommend one office electronic device. My required price in USD is at most 89.99.

Persona: My required color is exactly Pink.

```json
{
  "clarifications": [
    {
      "question_id": "weight",
      "question": "What is your maximum device weight?",
      "answer": "My required weight in grams is at most 447.922465375.",
      "constraint_ids": [
        "weight"
      ],
      "trigger_keywords": [
        "weight",
        "mass"
      ]
    }
  ],
  "constraints": [
    {
      "id": "budget",
      "source": "query",
      "field": "price",
      "op": "lte",
      "value": 89.99,
      "evidence_ids": [
        "B01FB654PI:details:price",
        "B09H2JQD48:details:price",
        "B09X983942:details:price",
        "B0B5LDPJLD:details:price",
        "B0BKFX6FWW:details:price",
        "B0BKS1K986:details:price",
        "B0BWYJJLSF:details:price"
      ]
    },
    {
      "id": "color",
      "source": "persona",
      "field": "color",
      "op": "eq",
      "value": "Pink",
      "evidence_ids": [
        "B09H2JQD48:details:color",
        "B09X983942:details:color",
        "B0B5LDPJLD:details:color",
        "B0BKS1K986:details:color",
        "B0BWYJJLSF:details:color"
      ]
    },
    {
      "id": "weight",
      "source": "clarification",
      "field": "weight_g",
      "op": "lte",
      "value": 447.922465375,
      "evidence_ids": [
        "B01FB654PI:details:weight_g",
        "B09H2JQD48:details:weight_g",
        "B09X983942:details:weight_g",
        "B0B5LDPJLD:details:weight_g",
        "B0BKFX6FWW:details:weight_g",
        "B0BKS1K986:details:weight_g",
        "B0BWYJJLSF:details:weight_g"
      ]
    }
  ],
  "feasible_product_ids": [
    "B0B5LDPJLD"
  ]
}
```

程序独立重算解集一致：`True`。这只是程序检查，不是人工通过。

同 root 任务：`task-9e9c41995b5779485caa` (base), `task-9e9c41995b5779485caa-cf-018340a0` (counterfactual)

待核对：原句/单位；完整合法解；隐藏渠道分离；家族身份；单约束反事实；表达保真与实际任务难度。

### task-ac53e878d2c50893225c (base, train)

任务 SHA：`12088c0e67166803c7be92f31c780cab9ed52682c6d79df6a61bf844bc41fcf0`；root：`task-ac53e878d2c50893225c`。

Query: Please recommend one office electronic device. My required price in USD is at most 34.99.

Persona: My required color is exactly White.

```json
{
  "clarifications": [
    {
      "question_id": "weight",
      "question": "What is your maximum device weight?",
      "answer": "My required weight in grams is at most 780.1788764.",
      "constraint_ids": [
        "weight"
      ],
      "trigger_keywords": [
        "weight",
        "mass"
      ]
    }
  ],
  "constraints": [
    {
      "id": "budget",
      "source": "query",
      "field": "price",
      "op": "lte",
      "value": 34.99,
      "evidence_ids": [
        "B01FB654PI:details:price",
        "B09H2JQD48:details:price",
        "B09X983942:details:price",
        "B0B5LDPJLD:details:price",
        "B0BKFX6FWW:details:price",
        "B0BKS1K986:details:price",
        "B0BWYJJLSF:details:price"
      ]
    },
    {
      "id": "color",
      "source": "persona",
      "field": "color",
      "op": "eq",
      "value": "White",
      "evidence_ids": [
        "B09H2JQD48:details:color",
        "B09X983942:details:color",
        "B0B5LDPJLD:details:color",
        "B0BKS1K986:details:color",
        "B0BWYJJLSF:details:color"
      ]
    },
    {
      "id": "weight",
      "source": "clarification",
      "field": "weight_g",
      "op": "lte",
      "value": 780.1788764,
      "evidence_ids": [
        "B01FB654PI:details:weight_g",
        "B09H2JQD48:details:weight_g",
        "B09X983942:details:weight_g",
        "B0B5LDPJLD:details:weight_g",
        "B0BKFX6FWW:details:weight_g",
        "B0BKS1K986:details:weight_g",
        "B0BWYJJLSF:details:weight_g"
      ]
    }
  ],
  "feasible_product_ids": [
    "B09X983942",
    "B0BWYJJLSF"
  ]
}
```

程序独立重算解集一致：`True`。这只是程序检查，不是人工通过。

同 root 任务：`task-ac53e878d2c50893225c` (base), `task-ac53e878d2c50893225c-cf-5ee29266` (counterfactual)

待核对：原句/单位；完整合法解；隐藏渠道分离；家族身份；单约束反事实；表达保真与实际任务难度。

### task-ac53e878d2c50893225c-cf-5ee29266 (counterfactual, train)

任务 SHA：`4870fa81199a95c22430afdb9a6ba68700c47c4040af3875545e705cbb2ab116`；root：`task-ac53e878d2c50893225c`。

Query: Please recommend one office electronic device. My required price in USD is at most 34.99.

Persona: My required color is exactly Baby Pink.

```json
{
  "clarifications": [
    {
      "question_id": "weight",
      "question": "What is your maximum device weight?",
      "answer": "My required weight in grams is at most 780.1788764.",
      "constraint_ids": [
        "weight"
      ],
      "trigger_keywords": [
        "weight",
        "mass"
      ]
    }
  ],
  "constraints": [
    {
      "id": "budget",
      "source": "query",
      "field": "price",
      "op": "lte",
      "value": 34.99,
      "evidence_ids": [
        "B01FB654PI:details:price",
        "B09H2JQD48:details:price",
        "B09X983942:details:price",
        "B0B5LDPJLD:details:price",
        "B0BKFX6FWW:details:price",
        "B0BKS1K986:details:price",
        "B0BWYJJLSF:details:price"
      ]
    },
    {
      "id": "color",
      "source": "persona",
      "field": "color",
      "op": "eq",
      "value": "Baby Pink",
      "evidence_ids": [
        "B09H2JQD48:details:color",
        "B09X983942:details:color",
        "B0B5LDPJLD:details:color",
        "B0BKS1K986:details:color",
        "B0BWYJJLSF:details:color"
      ]
    },
    {
      "id": "weight",
      "source": "clarification",
      "field": "weight_g",
      "op": "lte",
      "value": 780.1788764,
      "evidence_ids": [
        "B01FB654PI:details:weight_g",
        "B09H2JQD48:details:weight_g",
        "B09X983942:details:weight_g",
        "B0B5LDPJLD:details:weight_g",
        "B0BKFX6FWW:details:weight_g",
        "B0BKS1K986:details:weight_g",
        "B0BWYJJLSF:details:weight_g"
      ]
    }
  ],
  "feasible_product_ids": [
    "B09H2JQD48"
  ]
}
```

程序独立重算解集一致：`True`。这只是程序检查，不是人工通过。

同 root 任务：`task-ac53e878d2c50893225c` (base), `task-ac53e878d2c50893225c-cf-5ee29266` (counterfactual)

待核对：原句/单位；完整合法解；隐藏渠道分离；家族身份；单约束反事实；表达保真与实际任务难度。

### task-eab64e1f7a0884441a5f (base, train)

任务 SHA：`e03e1cbdf0c80cc99b77a5906313ee288bc945c1bafda1be67a5d38cee5e4f97`；root：`task-eab64e1f7a0884441a5f`。

Query: Please recommend one office electronic device. My required price in USD is at most 19.99.

Persona: My required color is exactly White.

```json
{
  "clarifications": [
    {
      "question_id": "weight",
      "question": "What is your maximum device weight?",
      "answer": "My required weight in grams is at most 616.8856232.",
      "constraint_ids": [
        "weight"
      ],
      "trigger_keywords": [
        "weight",
        "mass"
      ]
    }
  ],
  "constraints": [
    {
      "id": "budget",
      "source": "query",
      "field": "price",
      "op": "lte",
      "value": 19.99,
      "evidence_ids": [
        "B01FB654PI:details:price",
        "B09H2JQD48:details:price",
        "B09X983942:details:price",
        "B0B5LDPJLD:details:price",
        "B0BKFX6FWW:details:price",
        "B0BKS1K986:details:price",
        "B0BWYJJLSF:details:price"
      ]
    },
    {
      "id": "color",
      "source": "persona",
      "field": "color",
      "op": "eq",
      "value": "White",
      "evidence_ids": [
        "B09H2JQD48:details:color",
        "B09X983942:details:color",
        "B0B5LDPJLD:details:color",
        "B0BKS1K986:details:color",
        "B0BWYJJLSF:details:color"
      ]
    },
    {
      "id": "weight",
      "source": "clarification",
      "field": "weight_g",
      "op": "lte",
      "value": 616.8856232,
      "evidence_ids": [
        "B01FB654PI:details:weight_g",
        "B09H2JQD48:details:weight_g",
        "B09X983942:details:weight_g",
        "B0B5LDPJLD:details:weight_g",
        "B0BKFX6FWW:details:weight_g",
        "B0BKS1K986:details:weight_g",
        "B0BWYJJLSF:details:weight_g"
      ]
    }
  ],
  "feasible_product_ids": [
    "B09X983942"
  ]
}
```

程序独立重算解集一致：`True`。这只是程序检查，不是人工通过。

同 root 任务：`task-eab64e1f7a0884441a5f` (base)

待核对：原句/单位；完整合法解；隐藏渠道分离；家族身份；单约束反事实；表达保真与实际任务难度。

