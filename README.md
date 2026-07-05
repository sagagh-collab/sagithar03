# סוכן AI ל-Gmail ו-Calendar

**מטלת בונוס L08 — קוד קבוצה: `sagithar03`**

סוכן בינה מלאכותית שסורק תיבת Gmail בחיפוש אחר בקשות חופשיות (בטקסט חופשי) לקביעת
פגישות, משתמש במודל השפה Gemini כדי להבין ולחלץ את פרטי הפגישה, בודק זמינות
ב-Google Calendar, ולבסוף או קובע את הפגישה או משיב שהמועד המבוקש אינו זמין.

לפרטים המלאים ראו [`PRD.md`](./PRD.md) (מסמך דרישות), [`PLAN.md`](./PLAN.md)
(תוכנית הפיתוח), ו-[`TODO.md`](./TODO.md) (מעקב משימות).

## איך זה עובד

1. מתחברת ל-Google באמצעות OAuth 2.0 (הרשאות Gmail + Calendar).
2. קוראת הודעות מתיבת הדואר הנכנס מה-48 השעות האחרונות (ניתן להגדרה).
3. מדלגת על מיילים שהם הזמנות פורמליות ליומן (`.ics`) - רק בקשות בטקסט חופשי
   מטופלות.
4. שולחת כל מייל שנותר ל-Gemini (`gemini-2.5-flash`) כדי לסווג האם זו בקשה
   אמיתית לפגישה, ואם כן - לחלץ תאריך, שעה, משך, משתתפים, ומקום.
5. בודקת זמינות ביומן (Free/Busy) עבור פרק הזמן שחולץ.
6. **פנוי** ← יוצרת אירוע ביומן עם כל הפרטים.
   **תפוס** ← משיבה לשולח שהמועד תפוס.

## התקנה

### 1. דרישות מקדימות
- Python 3.10 ומעלה
- מנהל החבילות [`uv`](https://astral.sh/uv)
- חשבון Google (Gmail + Calendar)
- מפתח Gemini API חינמי ([Google AI Studio](https://aistudio.google.com))

### 2. הגדרת Google Cloud / OAuth
הוראות מלאות שלב-אחר-שלב מופיעות במדריך שסופק בקורס (נספח א'). בקצרה:
1. יצירת פרויקט ב-Google Cloud.
2. הפעלת **Gmail API** ו-**Google Calendar API**.
3. הגדרת מסך הסכמת ה-OAuth (קהל יעד External).
4. הוספת ההרשאות (scopes): `gmail.modify`, `calendar`.
5. יצירת OAuth Client מסוג **Desktop app**, הורדתו, ושמירתו בשם `credentials.json`
   בתיקייה זו.
6. הוספת כתובת המייל שלך כ-Test User (נדרש כל עוד האפליקציה במצב Testing).

### 3. מפתח Gemini API
1. כניסה ל-[aistudio.google.com](https://aistudio.google.com).
2. יצירת מפתח API (שכבה חינמית, ללא צורך בכרטיס אשראי).
3. יצירת קובץ בשם `.env` בתיקייה זו עם השורה:
   ```
   GEMINI_API_KEY=המפתח_שלך_כאן
   ```

### 4. התקנת תלויות
```bash
uv sync
```

### 5. הרצה
```bash
uv run main.py
```

בהרצה הראשונה ייפתח חלון דפדפן להתחברות ואישור הרשאות מול Google. נוצר קובץ
`token.json` שישמש בהרצות הבאות (אין צורך בהתחברות חוזרת, אלא אם התוקף פג או
שההרשאות משתנות).

## הגדרות ניתנות לשינוי

ניתן לערוך את הקבועים בראש הקובץ `main.py`:

| קבוע | ברירת מחדל | תיאור |
|---|---|---|
| `LOOKBACK_HOURS` | `48` | כמה שעות אחורה לסרוק בתיבת הדואר |
| `GEMINI_MODEL` | `gemini-2.5-flash` | איזה מודל Gemini לשימוש |
| `DEFAULT_MEETING_DURATION_MINUTES` | `60` | משך ברירת מחדל כשלא מצוין במייל |

## הערות אבטחה

הקבצים הבאים מכילים מידע רגיש ו**מוחרגים מהריפו** באמצעות `.gitignore`:
- `credentials.json` — סוד ה-OAuth Client
- `token.json` — טוקן הגישה/ריענון האישי
- `.env` — מפתח ה-Gemini API

כדי להריץ את הפרויקט בעצמכם, יש ליצור עותקים אישיים של קבצים אלה לפי השלבים
לעיל.

## דוגמת הרצה

```
Found 8 email(s) from the last 48 hours.

[created] '...' -> event 754q0c9rs9vg9pjlmskqi9qrug (https://www.google.com/calendar/event?eid=...)
[created] '...' -> event mrkcch971t2tu1e4fo95gh6i0c (https://www.google.com/calendar/event?eid=...)
[skip] 'ניוזלטר בעברית' - not a meeting request
[skip] 'SUMMER SALE ...' - no text body
[skip] 'Due on ...' - not a meeting request
[skip] 'Movistar Movil - Recibo Digital Julio 2026' - not a meeting request
[skip] 'Mejora tu experiencia móvil...' - not a meeting request
```

מתוך 8 מיילים אמיתיים בתיבת הדואר (בעברית, אנגלית וספרדית), הסוכן זיהה נכון 2
בקשות אמיתיות לפגישה וקבע אותן, תוך דילוג נכון על ניוזלטרים, חשבוניות,
והתכתבויות לא רלוונטיות.

## צילומי מסך

<img width="1436" height="1165" alt="collage_1_cloud_setup" src="https://github.com/user-attachments/assets/e56ed22c-308c-429b-8bbc-e058185a9388" />

<img width="1436" height="692" alt="collage_5_client_token" src="https://github.com/user-attachments/assets/b9d1b56d-ca3e-46af-98ab-741e598f5362" />

<img width="1436" height="771" alt="collage_2_connectivity_test" src="https://github.com/user-attachments/assets/a0ad31ca-29b2-4881-a931-8ee3dc87907b" />

<img width="1224" height="442" alt="collage_3_agent_run" src="https://github.com/user-attachments/assets/eedf9e64-1257-46ee-ad83-554c48d5232e" />

<img width="924" height="260" alt="collage_4_calendar_results" src="https://github.com/user-attachments/assets/1cf2da61-09e2-4f6d-8e09-25eb3edab35d" />

## מבנה הפרויקט

```
.
├── main.py            # הסוכן
├── pyproject.toml      # תלויות
├── uv.lock             # גרסאות תלויות נעולות
├── PRD.md               # מסמך דרישות המוצר
├── PLAN.md              # תוכנית הפיתוח
├── TODO.md              # מעקב משימות
├── README.md            # קובץ זה
└── .gitignore           # מחריג credentials.json, token.json, .env וכו'
```
