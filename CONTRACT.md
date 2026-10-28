# CONTRACT.md — сайт учебного центра (Kwork, заказчик mirprof)

## 1. ТЗ заказчика (дословно)
> Сайт учебного центра. Приветствую! Нам нужен сайт образовательной организации (Учебный центр), Простой, доступный, краткий
> (мы обучаем Охрана труда, пожарная безопасность, рабочие профессии и т.д.). и он должен соответствовать требованиям
> Приказа Рособрнадзора от 04.08.2023 № 1493. Можно сделать и копию сайта. Направьте ссылку на выполненные работы.
> Цена до: 10 000 ₽.

Цель: демо, которое можно показать ссылкой, + проект, который можно сразу развернуть заказчику.
Действующая редакция приказа № 1493 — с изменениями приказов № 1353 от 03.07.2025 и № 920 от 30.04.2026 (действует с 01.09.2026).
Полный текст требований: `research/REQUIREMENTS_1493.md` (пишет оркестратор — уже лежит).

Демо-организация (вымышленная, везде помечать «демо-данные»):
**АНО ДПО «Учебный центр «Профресурс»»**, г. Самара (адрес, ИНН, лицензия — вымышленные, правдоподобные).
Направления: охрана труда, пожарная безопасность, первая помощь, рабочие профессии (стропальщик, сварщик, электромонтёр,
тракторист? — нет, только без прав: стропальщик, рабочий люльки, электросварщик, слесарь-ремонтник, оператор котельной),
электробезопасность, промышленная безопасность, ГО и ЧС.

## 2. Стек
Django 5.2 (ASGI, async views где есть ORM-чтение, uvicorn), собственный CSS, vanilla JS (без HTMX — не нужен), SQLite (dev) /
PostgreSQL (prod через DATABASE_URL, `dj-database-url`), WhiteNoise, python-dotenv, reportlab (демо-PDF), httpx (Telegram).
Никаких CDN и Google Fonts. Шрифт — системный стек + локальный (если нужен, кладётся в static/fonts).
Python 3.12+. Язык интерфейса — русский. TIME_ZONE = "Europe/Samara".

## 3. Владение файлами (чужие файлы НЕ трогать — нужные правки описывать в отчёте)
| Владелец | Файлы |
|---|---|
| orchestrator | CONTRACT.md, research/REQUIREMENTS_1493.md |
| backend-dev | config/*, core/{models,admin,forms,views,urls,context_processors,notify,apps}.py, core/management/**, core/migrations/**, sveden/{models,admin,views,urls,apps,demo_pdf}.py, sveden/migrations/**, */tests*.py, requirements.txt |
| frontend-dev | templates/base.html, templates/core/**, templates/sveden/**, templates/admin/** (оформление админки, опционально), static/** |
| copywriter-seo | seed/demo_content.json, templates/legal/*.html, core/content.py, docs/SEO.md |
| devops | Dockerfile, docker-compose.yml, deploy/**, .env.example, .gitignore, .dockerignore, scripts/**, README.md, DEPLOY.md, .github/** |
| researcher | research/RESEARCH.md, research/ITEMPROP.md |

## 4. URL (имена неизменны)
| URL | name | view | шаблон |
|---|---|---|---|
| `/` | `core:home` | home | core/home.html |
| `/obuchenie/` | `core:program_list` | program_list (GET `?cat=<slug>` фильтр) | core/program_list.html |
| `/obuchenie/<slug>/` | `core:program_detail` | program_detail | core/program_detail.html |
| `/kontakty/` | `core:contacts` | contacts | core/contacts.html |
| `/zayavka/` (POST) | `core:lead_create` | lead_create → redirect `core:lead_success`; при ошибках рендер core/lead_form_page.html (контекст `form`) | core/lead_form_page.html |
| `/zayavka/spasibo/` | `core:lead_success` | | core/lead_success.html |
| `/politika/` | `core:privacy` | | core/privacy.html (внутри `{% include "legal/privacy_text.html" %}`) |
| `/soglasie/` | `core:consent` | | core/consent.html (внутри `{% include "legal/consent_text.html" %}`) |
| `/sveden/` | `sveden:index` | | sveden/index.html |
| `/sveden/common/` | `sveden:common` | | sveden/common.html |
| `/sveden/struct/` | `sveden:struct` | | sveden/struct.html |
| `/sveden/document/` | `sveden:document` | | sveden/document.html |
| `/sveden/education/` | `sveden:education` | | sveden/education.html |
| `/sveden/eduStandarts/` | `sveden:eduStandarts` | | sveden/eduStandarts.html |
| `/sveden/managers/` | `sveden:managers` | | sveden/managers.html |
| `/sveden/employees/` | `sveden:employees` | | sveden/employees.html |
| `/sveden/objects/` | `sveden:objects` | | sveden/objects.html |
| `/sveden/paid_edu/` | `sveden:paid_edu` | | sveden/paid_edu.html |
| `/sveden/budget/` | `sveden:budget` | | sveden/budget.html |
| `/sveden/vacant/` | `sveden:vacant` | | sveden/vacant.html |
| `/sveden/grants/` | `sveden:grants` | | sveden/grants.html |
| `/sveden/inter/` | `sveden:inter` | | sveden/inter.html |
| `/sveden/catering/` | `sveden:catering` | | sveden/catering.html |
| `/admin/` | панель заказчика (Django admin, русские названия) | | |
| `/robots.txt`, `/sitemap.xml` | `robots`, `django.contrib.sitemaps` | | |

Все `sveden/*.html` наследуют `sveden/base_sveden.html` (extends base.html): хлебные крошки + **боковое меню всех 14 подразделов на
каждой странице** (п. 2 Требований) + `{% block sveden_content %}`. Каждая страница подраздела показывает дату обновления
`page_updated` (дата последнего изменения данных).

## 5. Контекст
### Context processor `core.context_processors.site` (на всех страницах)
- `org` — `sveden.Organization` (singleton, может быть None — шаблоны должны это переживать)
- `nav_categories` — list[ProgramCategory]
- `sveden_sections` — list[dict(slug, title, url)] в порядке п. 6 приказа (13 + eduStandarts после education)
- `lead_form` — пустая `LeadForm`
- `consent_version` — строка, напр. "1.0 от 27.10.2026"
- `site_demo` — bool (settings.SITE_DEMO, env SITE_DEMO=1 → показывать плашку «Демо-версия, данные вымышленные»)

### Views
- home: `popular_programs` (list[Program], is_popular), `categories` (list[ProgramCategory] с `.programs_count`), `advantages`, `faq`, `steps` (из core/content.py — списки dict(title, text)), `stats` (list dict(value, label))
- program_list: `categories`, `programs` (list), `active_category` (ProgramCategory|None)
- program_detail: `program`, `related` (list[Program] той же категории, ≤3)
- contacts: только context processor
- sveden:index: `sections` (= sveden_sections)
- sveden:common: `org`, `founders`, `places` (list[EduPlace])
- sveden:struct: `departments`, `docs` (Document section="struct")
- sveden:document: `docs` (Document section="document"), `prescriptions_text` (str, напр. "Предписаний нет")
- sveden:education: `programs` (list[Program] опубликованные), `docs` (section="education"), `fields` (SvedenField page="education")
- sveden:eduStandarts: `fields`, `docs` (section="eduStandarts")
- sveden:managers: `head` (Manager|None), `deputies` (list[Manager])
- sveden:employees: `teachers` (list[Teacher] с prefetch programs)
- sveden:objects: `facilities` (list[Facility]), `fields`, `docs` (section="objects")
- sveden:paid_edu: `docs` (section="paid_edu"), `programs` (для таблицы стоимости), `fields`
- sveden:budget: `fields`, `docs` (section="budget")
- sveden:vacant: `vacancies` (list[VacantPlace] select_related program)
- sveden:grants / inter / catering: `fields`, `docs` (section=slug)
- Во всех sveden-view: `page_updated` (date), `section` (dict текущего подраздела)

## 6. Модели (поля неизменны, verbose_name — по-русски)
### core
- **ProgramCategory**: name, slug(unique), short(Text, blank), icon(Char: one of `shield, fire, helmet, cross, bolt, crane, weld, factory`), order(int)
- **Program**: category(FK, related_name="programs"), title, slug(unique), kind(Char choices: `ot` "Обучение по охране труда", `pk` "Повышение квалификации", `pp` "Профессиональная переподготовка", `po` "Профессиональное обучение"), code(Char blank — код профессии ОКПДТР для ПО), hours(PositiveInt), duration(Char, напр. "5 дней"), form(Char, напр. "Очная, очно-заочная, с применением ДОТ"), price(PositiveInt, руб.), document_issued(Char), short(Text), description(Text), audience(Text blank), disciplines(Text — по строке на модуль), practice(Text blank), language(Char default "Русский"), is_popular(bool), is_published(bool, default True), order(int), op_file/plan_file/schedule_file/rpd_file/methodology_file (FileField blank, upload_to="programs/").
  Свойства: `level_display` ("Дополнительное профессиональное образование" для pk/pp/ot, "Профессиональное обучение" для po), `disciplines_list` (list[str]), `get_absolute_url()`.
- **Lead**: name(Char 120), phone(Char 30), email(blank), organization(Char blank), program(FK null, SET_NULL), comment(Text blank, max 2000), consent(bool), consent_version(Char), consent_at(DateTime null), ip(GenericIPAddress null), created_at(auto), status(choices `new` Новая/`work` В работе/`done` Обработана/`spam` Спам), staff_note(Text blank).
### sveden
- **Organization** (singleton pk=1): full_name, short_name, reg_date(Date), address, work_time(Text), phones(Char), emails(Char), inn, ogrn, license_number, license_date(Date null), license_issuer, license_url(URL blank — выписка из реестра лицензий), license_file(File blank), accreditation_note(Text, default "Государственная аккредитация по программам ДПО и профессионального обучения не проводится (ст. 92 Федерального закона № 273-ФЗ)"), map_embed_url(URL blank), updated_at(auto_now).
- **Founder**: name, address, phone, email, website, order
- **EduPlace**: kind(choices `dop` (itemprop addressPlaceDop), `oppo` (addressPlaceOppo), `prac` (addressPlacePrac), `podg` (addressPlacePodg), `set` (addressPlaceSet)), address, order. Свойство `itemprop`.
- **Department**: name, head_fio, head_post, address, site(blank), email(blank), clause_file(File blank), order
- **Document**: section(choices = slugs подразделов), itemprop(Char blank — напр. `ustavDocLink`), title, file(File blank, upload_to="docs/"), url(URL blank), number(blank), doc_date(Date null), signed(bool — подписан ЭП), signer(Char blank — «Иванов И.И., директор»), signed_at(DateTime null), order, is_published. Свойство `link` (file.url или url), `updated_at`(auto_now).
- **Manager**: role(choices `head` (itemprop rucovodstvo) / `zam` (rucovodstvoZam)), fio, post, phone, email, photo(Image blank — без Pillow НЕ использовать ImageField: FileField), order
- **Teacher**: fio, post, disciplines(Text), level(Text — уровень образования, специальность, квалификация), degree(default "Нет"), academic_title(default "Нет"), qualification(Text — ПК за 3 года), retraining(Text blank), experience(PositiveSmallInt — лет), programs(M2M Program, blank), order
- **Facility**: kind(choices `cab` учебный кабинет, `prac` объект для практических занятий, `libr` библиотека, `sport` объект спорта), name, address, equipment(Text), ovz(Text — приспособленность для инвалидов и лиц с ОВЗ), order
- **VacantPlace**: program(FK), fed, sub, mest, paid (PositiveInt, default 0)
- **SvedenField**: page(choices = slugs подразделов), itemprop(Char), label(Char), value(Text — переносы строк сохраняются, `|linebreaksbr`), order
- Все модели sveden имеют `updated_at = DateTimeField(auto_now=True)`.

## 7. Микроразметка itemprop (п. 27 Требований; методические рекомендации Рособрнадзора)
Проверенные (из методических рекомендаций 2025, research/REQUIREMENTS_1493.md):
- `copy` — ссылка «Версия для слабовидящих» в шапке (на главной и на каждой странице раздела)
- common: `fullName`, `shortName`, `regDate`, `address`, `workTime`, `telephone`, `email` (каждый — на td со значением);
  учредитель: `<tr itemprop="uchredLaw">` c `nameUchred`, `addressUchred`, `telUchred`, `mailUchred`, `websiteUchred`;
  `licenseDocLink` (на `<a>`); места: `<tr itemprop="addressPlaceDop|addressPlaceOppo|...">`.
- struct: `<tr itemprop="structOrgUprav">` → `name`, `fio`, `post`, `addressStr`, `site`, `email`, `divisionClauseDocLink` (a)
- document: на `<a>`: `ustavDocLink`, `localActStud`, `localActOrder`, `localActCollec`, `reportEduDocLink`, `prescriptionDocLink`, `priemDocLink`, `modeDocLink`, `tekKontrolDocLink`, `perevodDocLink`, `vozDocLink` (значение берётся из `doc.itemprop`)
- education: `<tr itemprop="eduAccred">` → `eduCode`, `eduName`, `eduProf`, `eduLevel`, `eduForm`, `learningTerm`, `eduPred`, `eduPrac`;
  `<tr itemprop="eduOp">` → `eduCode`, `eduName`, `eduLevel`, `eduProf`, `eduForm`, ссылки `opMain`, `educationPlan`, `educationRpd`, `educationShedule`, `methodology`;
  ссылки `languageEl`, `eduChislenEl`, `eduPriemEl`, `eduPerevodEl` (из docs по doc.itemprop)
- eduStandarts: `eduFedDoc`, `eduStandartDoc`, `eduFedTreb`, `eduStandartTreb` (на a)
- managers: `<tr itemprop="rucovodstvo">` / `<tr itemprop="rucovodstvoZam">` → `fio`, `post`, `telephone`, `email`
- employees: `<tr itemprop="teachingStaff">` → `fio`, `post`, `teachingDiscipline`, `teachingLevel`, `degree`, `academStat`, `qualification`, `profDevelopment`, `specExperience`, `teachingOp`
- objects: `<tr itemprop="purposeCab">` → `addressCab`, `nameCab`, `osnCab`, `ovzCab`; `<tr itemprop="purposePrac">` → `addressPrac`, `namePrac`, `osnPrac`, `ovzPrac`;
  libr/sport — по research/ITEMPROP.md (до его готовности: `purposeLibr`/`purposeSport` с `objName`, `objAddress`, `objCnt`, `objOvz`)
- vacant (до проверки research): `<tr itemprop="vacant">` → `eduCode`, `eduName`, `eduLevel`, `eduForm`, `numberBFVacant`, `numberBRVacant`, `numberBMVacant`, `numberPVacant`
- paid_edu / budget / grants / inter / catering / прочие текстовые сведения — через **SvedenField** (`<div itemprop="{{ f.itemprop }}">`) и **Document** (`<a itemprop="{{ doc.itemprop }}">`). Имена itemprop для них — в seed (copywriter) по research/ITEMPROP.md.
- Отсутствующие сведения выводить текстом «Отсутствует» / «Нет» внутри элемента с itemprop (не пропускать элемент).
- На главной `sveden:index` — ссылки на подразделы (до 10 могут иметь `itemprop="addRef"` — не обязательно).

## 8. Форма заявки `core.forms.LeadForm`
Поля (имена неизменны): `name`, `phone`, `email`, `organization`, `program` (ModelChoice, необязательно), `comment`, `consent` (BooleanField required, не отмечен), `website` (honeypot, скрыт CSS-классом `hp`, должен быть пустым).
POST на `{% url 'core:lead_create' %}`, `{% csrf_token %}`. Можно передать `program` скрытым полем со страницы программы (`?program=<pk>` или initial).
Rate-limit: не более 5 заявок с IP за 10 минут (cache). Валидация телефона: 10–15 цифр.
Чекбокс согласия — текст: «Я даю [согласие на обработку персональных данных](core:consent) и ознакомлен с [политикой](core:privacy)».
Уведомления: email (если EMAIL_HOST задан) + Telegram (если TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID) — **только** «Новая заявка #id» + ссылка в админку, без ПДн.

## 9. Версия для слабовидящих (frontend)
Кнопка в шапке `<a href="#" itemprop="copy" id="a11y-toggle">Версия для слабовидящих</a>` → панель: размер шрифта (3 уровня),
цветовая схема (обычная / чёрное на белом / белое на чёрном / синее на голубом), изображения вкл/выкл, межбуквенный интервал,
«Обычная версия». Классы на `<html>`: `a11y`, `a11y-fs-1|2|3`, `a11y-cs-bw|wb|blue`, `a11y-noimg`, `a11y-ls-2`. Хранение — localStorage (try/catch).
Без JS сайт полностью работает.

## 10. Env-переменные
SECRET_KEY, DEBUG (0/1), ALLOWED_HOSTS (через запятую), CSRF_TRUSTED_ORIGINS, DATABASE_URL, SITE_URL (для ссылок в уведомлениях и sitemap),
SITE_DEMO (0/1), EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, EMAIL_USE_SSL, DEFAULT_FROM_EMAIL, LEADS_EMAIL_TO,
TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, SECURE_SSL_REDIRECT (0/1).

## 11. Демо-данные `seed/demo_content.json` (copywriter) → `python manage.py seed_demo [--reset]` (backend)
Схема (ключи = модели, значения = списки объектов с полями из п. 6; FK по slug/ключу):
```json
{
  "organization": {...поля Organization; даты "YYYY-MM-DD"},
  "founders": [{...}],
  "edu_places": [{"kind": "dop", "address": "..."}],
  "categories": [{"name","slug","short","icon","order"}],
  "programs": [{"category": "<slug>", "title","slug","kind","code","hours","duration","form","price","document_issued","short","description","audience","disciplines": "строка1\nстрока2","practice","is_popular","order"}],
  "departments": [{...}],
  "documents": [{"section","itemprop","title","number","doc_date","signed": true,"signer","order"}],
  "managers": [{...}],
  "teachers": [{..., "programs": ["<program slug>", ...]}],
  "facilities": [{...}],
  "vacant": [{"program": "<slug>", "fed":0,"sub":0,"mest":0,"paid":12}],
  "fields": [{"page","itemprop","label","value","order"}]
}
```
`seed_demo` для каждого Document без файла и для op_file/plan_file/... программ генерирует демо-PDF (reportlab, шрифт DejaVuSans,
крупная надпись «ДЕМО-ДОКУМЕНТ», штамп «Документ подписан простой электронной подписью: <signer>, <дата>») в MEDIA_ROOT.
Также создаёт суперпользователя `admin` / пароль из env `DEMO_ADMIN_PASSWORD` (если задан).

## 12. Статическая демо-копия (devops: scripts/export_static.py)
Рендерит все URL через `django.test.Client` (SITE_DEMO=1) в `dist/`, страницы как `<path>/index.html`, **все внутренние ссылки
переписывает в относительные** (`../sveden/common/index.html`), копирует static и media, формы заменяет: `action` → `#` +
атрибут `data-demo` (frontend JS показывает «В демо-версии форма не отправляется»). Ссылка `/admin/` в демо убирается.

## 13. Изменения после проверки (фаза 4)
- LeadForm: + `listeners` (1–500, необяз.), `need_invoice` (bool); Lead: + listeners, need_invoice; `Lead.__str__` = «Заявка #N».
- Подпись `consent` — только «Я даю согласие на обработку ПДн» (ссылка на /soglasie/); ссылка на политику — отдельной строкой рядом.
- Телефон хранится нормализованным (+7XXXXXXXXXX).
- VacantPlace.program — OneToOneField (related_name="vacant_place"); `/sveden/vacant/` выводит все опубликованные программы (нули, если записи нет).
- EduPlace.kind: + `gia` (addressPlaceGia). Department.clause_file — демо-PDF из seed_demo; Document section="struct" не используется.
- Context processor: + `canonical_url`. Все публичные views — `require_safe` (GET и HEAD).
- FileField: валидация расширений и размера ≤ 20 МБ. Founder.website, Department.site — URLField.
- env: SITE_DEMO=0 по умолчанию, MEDIA_ROOT, LEAD_RETENTION_DAYS, LEAD_SPAM_RETENTION_DAYS, CSP_REPORT_ONLY, SECURE_HSTS_PRELOAD.
- CSP строгий (core/middleware.py): никаких inline-скриптов и style-атрибутов на публичных страницах.
