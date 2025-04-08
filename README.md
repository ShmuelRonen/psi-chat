# מערכת ניתוח תודעתי

מערכת המאפשרת ניתוח תודעתי דרך שיחה טבעית ומעניינת עם DeepSeek R1.

## תכונות עיקריות

- שיחה טבעית וזורמת
- התאמה אישית של קצב ועומק השאלות
- שילוב הומור במידה מתונה
- ניתוח תודעתי מעמיק
- ממשק API פשוט לשימוש
- תמיכה מעולה בעברית

## התקנה

1. התקן את התלויות:
```bash
pip install -r requirements.txt
```

2. צור קובץ `.env` עם המפתח שלך ל-DeepSeek API:
```
DEEPSEEK_API_KEY=yours R1 api key
```
שים לב: קובץ ה-.env צריך להיות בפורמט של זוגות מפתח-ערך, כל שורה מכילה זוג אחד, ללא סוגריים מסולסלים או גרשיים מיותרים.

3. הפעל את השרת:
```bash
python main.py
```

## שימוש ב-API

### התחלת שיחה חדשה
```bash
curl -X POST http://localhost:8000/start
```

### המשך שיחה
```bash
curl -X POST http://localhost:8000/continue \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "תשובת המשתמש"}]}'
```

### ניתוח השיחה
```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "תשובת המשתמש"}]}'
```

## פיתוח עתידי

- [ ] הוספת ממשק משתמש ויזואלי
- [ ] שיפור מנגנון הניתוח
- [ ] הוספת יכולת שמירה וטעינה של שיחות
- [ ] הרחבת יכולות הניתוח התודעתי
- [ ] הוספת תמיכה בשפות נוספות 