# ITEMPROP.md — микроразметка подразделов «Сведения об ОО» (дополнение к REQUIREMENTS_1493.md)

Автор: researcher. Обновлено: 28.10.2026 (v2: budget/vacant/inter/catering подтверждены вторым источником).

## 0. Какая версия рекомендаций актуальна (ВАЖНО)
- **9.0.0 (2025)** — https://db-nica.ru/documents/regulations/sveden/metodicheskie-rekomendaczii-2025.pdf, она же в КонсультантПлюс
  (cons_doc_LAW_177135, разделы 3.9/3.10/3.11 прочитаны полностью).
- **10.0.0 (2026, «Москва 2026»)** — уже вышла: новость ФРЦ ДС от 14.09.2026 https://www.frcds.ru/news-14-09-2026/ ,
  PDF https://www.frcds.ru/wp-content/uploads/2026/09/metod-rek-minobr-ver-10.0.0.pdf ; КонсультантПлюс тоже показывает
  титул «Версия 10.0.0» (https://www.consultant.ru/document/cons_doc_LAW_177135/), pravo.ppt.ru/metodicheskiye-rekomendatsii/353943.
  Прочитано (WebFetch отдаёт только ~78 тыс. символов, дальше п. 3.9 строка 7 не видно): таблицы 3.2.1, 3.5.1–3.5.8, 3.6.1,
  3.7.1, 3.8.1, 3.9.1 (строки 1–6) **совпадают с 9.0.0 по именам атрибутов**. Отличия 10.0.0, которые видны:
  - **`copy` в таблицах 10.0.0 не встречается** (в 9.0.0 он был строкой 1 каждой таблицы). Новость ФРЦ ДС: «исключена версия
    для слабовидящих». Пункт о версии для слабовидящих исключён из Приказа 1493 ещё редакцией № 1353 (2025) — db-nica.ru/blog.
    ⇒ **`itemprop="copy"` оставить можно (не вредит), но он больше не проверяемый пункт.** Саму версию для слабовидящих
    оставляем (доступность сайта для инвалидов по зрению — см. RESEARCH.md §3).
  - В 10.0.0 нумерация 3.9.1 сдвинулась (purposeCab = строка 1, т.к. нет `copy`), имена те же.
  - `accreditationDocLink` в 10.0.0 — строка 9 таблицы 3.5.1 (подраздел **education**, не common): «при отсутствии — «отсутствует»».
  - `napravNir` в 10.0.0 присутствует (строка 7.6 3.5.1). (По пересказу db-nica в 9.0.0 его удаляли — в 10.0.0 он есть; для нас
    неважно, eduNir не заполняем, т.к. научной деятельности нет — пишем текстом «не ведётся».)
- Таблицы 3.12–3.15 **ни в 9.0.0, ни в 10.0.0 прочитать самому не удалось** (WebFetch режет PDF на ~78 тыс. символов, КонсультантПлюс
  отдаёт только заголовок раздела). Для них основной источник — открытый словарь микроразметки **aplicon-ru/edu-framework**
  (`standards/sveden/vocab/base.yaml`, 0.1.0 от 2026-06-11, «выверен против МР v9.0.0, все 14 подразделов status: verified»)
  — https://github.com/aplicon-ru/edu-framework/tree/main/standards/sveden — плюс старые версии МР (2019 / «Актуализированные»).
  Это вторичный источник ⇒ отмечено «вероятно». **Перед продом прогнать сайт через АИС «Мониторинг» / сверить с полным PDF 10.0.0.**

## 1. Общие правила (9.0.0 и 10.0.0, подтверждено)
- Нет главного тега → `<div itemprop="X">значение</div>` (или `<span>`, `<p>`, `<td>`). Есть главный тег → дочерние **внутри** него
  (`<tr itemprop="main"><td itemprop="child">`).
- Ссылки на файлы (эл. документы) — `<a href="..." itemprop="X">Понятное название документа</a>`. Внутри файлов ничего не размечается.
- Нет сведений → размечаем слово **«отсутствует»** / «нет» (пример из 3.11: `<span itemprop="paidEdu">Отсутствует</span>`).
  Не пропускать элемент.
- Подписи пунктов (названия из таблиц рекомендаций) на экран не выводятся как требование — выводим нормальные заголовки по тексту приказа.
- Ссылки на доп. страницы подраздела — `itemprop="addRef"` (≤10).
- Обновление сведений — в течение 10 рабочих дней после изменения.
- Проверка — АИС «Мониторинг» Рособрнадзора (доступ бесплатно по запросу).
- В исходниках рекомендаций есть опечатки (`hosteInfo`, `" teachingOp"`, `teachingDisciplin e`, `<tditemprop`) — используем
  нормальное написание: `hostelInfo`, `teachingOp`, `teachingDiscipline`.

## 2. Таблица атрибутов (только то, чего нет в REQUIREMENTS_1493.md, + перепроверка education/eduStandarts)

Обозначения: «подтв.» = прочитано в тексте 9.0.0 (КонсультантПлюс / PDF) и/или 10.0.0; «вероятно» = из старых версий/пересказов.

### objects — «Материально-техническое обеспечение и оснащённость образовательного процесса. Доступная среда» (табл. 3.9.1 v9.0.0)
| подраздел | itemprop | где ставится | что размечает | источник | уверенность |
|---|---|---|---|---|---|
| objects | `purposeCab` | **tr** (главный) | строка «учебный кабинет» | 9.0.0 табл. 3.9.1 п.2, пример 3.9.2; 10.0.0 п.1 | подтв. |
| objects | `addressCab`, `nameCab`, `osnCab`, `ovzCab` | td | адрес / наименование / оснащённость / приспособленность для ОВЗ | то же | подтв. |
| objects | `purposePrac` | **tr** (главный) | строка «объект для практических занятий» | 9.0.0 п.3; 10.0.0 п.2 | подтв. |
| objects | `addressPrac`, `namePrac`, `osnPrac`, `ovzPrac` | td | адрес / наименование / оснащённость / ОВЗ | то же | подтв. |
| objects | `purposeLibr` | **tr** (главный) | строка «библиотека» (каждый объект/адрес — отдельная строка, табл. 3.9.3) | 9.0.0 п.4; 10.0.0 п.3 | подтв. |
| objects | `objName`, `objAddress`, `objOvz` | td (внутри purposeLibr) | наименование / адрес / приспособленность для ОВЗ | то же | подтв. |
| objects | `purposeSport` | **tr** (главный) | строка «объект спорта» (та же табл. 3.9.3) | 9.0.0 п.5; 10.0.0 п.4 | подтв. |
| objects | `objName`, `objAddress`, `objOvz` | td (внутри purposeSport) | наименование / адрес / ОВЗ | то же | подтв. |
| objects | `ovz` | div/p (текст) | обеспечение беспрепятственного доступа в здания для инвалидов и ОВЗ | 9.0.0 п.6; 10.0.0 п.5 | подтв. |
| objects | `purposeFacil` | div/p (текст) | средства обучения и воспитания | 9.0.0 п.7; 10.0.0 п.6 | подтв. |
| objects | `purposeFacilOvz` | div/p (текст) | средства обучения и воспитания, приспособленные для инвалидов/ОВЗ | 9.0.0 п.8 | подтв. |
| objects | `comNet` | div/p (текст) | доступ к информационным системам и ИТС сетям | 9.0.0 п.9 | подтв. |
| objects | `comNetOvz` | div/p (текст) | доступ к приспособленным для инвалидов/ОВЗ ИС и сетям | 9.0.0 п.10 | подтв. |
| objects | `erList` | **a** (список ссылок) | электронные образовательные ресурсы (ЭБС, ресурсы библиотеки и т.п.) | 9.0.0 п.11 + пример | подтв. |
| objects | `erListOvz` | **a** | ЭОР, приспособленные для инвалидов/ОВЗ | 9.0.0 п.12 + пример | подтв. |
| objects | `techOvz` | div/p (текст) | специальные технические средства обучения коллективного и индивидуального пользования | 9.0.0 п.13 | подтв. |
| objects | `hostelInfo` | td (табл. 3.9.4) | количество общежитий | 9.0.0 п.14 (в таблице опечатка `hosteInfo`, в примере `hostelInfo`) | подтв. |
| objects | `interInfo` | td | количество интернатов | 9.0.0 п.15 | подтв. |
| objects | `hostelNum` | td | количество мест в общежитиях | 9.0.0 п.16 | подтв. |
| objects | `hostelNumOvz` | td | кол-во жилых помещений в общежитии, приспособленных для ОВЗ | 9.0.0 п.17 | подтв. |
| objects | `interNum` | td | количество мест в интернатах | 9.0.0 п.18 | подтв. |
| objects | `interNumOvz` | td | кол-во жилых помещений в интернате, приспособленных для ОВЗ | 9.0.0 п.19 | подтв. |
| objects | `hostelInterOvz` | div/p (текст) | условия беспрепятственного доступа в общежитие/интернат | 9.0.0 п.20 | подтв. |
| objects | `localActObSt` | **a** (или текст) | документ о порядке формирования платы за проживание в общежитии | 9.0.0 п.21 + пример | подтв. |

Таблица 3.9.4 (общежития/интернаты) в 9.0.0 заполняется по организации в целом, в примере отсутствующее — **«0»**. Без главного тега
(td с атрибутами прямо в строке таблицы). Для учебного центра без общежития: hostelInfo=0, interInfo=0, hostelNum=0, hostelNumOvz=0,
interNum=0, interNumOvz=0, hostelInterOvz «Общежитие отсутствует», localActObSt «Отсутствует» (span).

> ⚠ Для 10.0.0 строки 7+ таблицы 3.9.1 не прочитаны. Новость ФРЦ ДС говорит о «новых требованиях к размещению информации об
> условиях доступности» — возможны новые атрибуты для ОВЗ. Строки 1–6 совпадают с 9.0.0.

**Пример (objects):**
```html
<table><tr itemprop="purposeLibr"><td itemprop="objName">Библиотека учебного центра</td>
  <td itemprop="objAddress">г. Самара, ул. ..., каб. 12</td><td itemprop="objOvz">Приспособлена: ...</td></tr></table>
<table><tr itemprop="purposeSport"><td itemprop="objName">Отсутствует</td><td itemprop="objAddress">Отсутствует</td>
  <td itemprop="objOvz">Отсутствует</td></tr></table>
<div itemprop="ovz">Вход оборудован пандусом, кнопкой вызова ...</div>
<div itemprop="purposeFacil">Тренажёр-манекен «Гоша», ...</div>
<div itemprop="purposeFacilOvz">...</div>
<div itemprop="comNet">Доступ к сети Интернет ...</div><div itemprop="comNetOvz">...</div>
<a href="..." itemprop="erList">ЭБС «...»</a> <a href="..." itemprop="erListOvz">Версия ЭБС для слабовидящих</a>
<div itemprop="techOvz">...</div>
<table><tr><td itemprop="hostelInfo">0</td><td itemprop="interInfo">0</td><td itemprop="hostelNum">0</td>
  <td itemprop="hostelNumOvz">0</td><td itemprop="interNum">0</td><td itemprop="interNumOvz">0</td></tr></table>
<div itemprop="hostelInterOvz">Общежитие и интернат отсутствуют</div>
<span itemprop="localActObSt">Отсутствует</span>
```

### grants — «Стипендии и меры поддержки обучающихся» (табл. 3.10.1 v9.0.0)
| подраздел | itemprop | где ставится | что размечает | источник | уверенность |
|---|---|---|---|---|---|
| grants | `grant` | div/p (текст или ссылки на документы) | наличие и условия предоставления стипендий. Нет стипендий → «Выплата стипендий не предусмотрена» | 9.0.0 табл. 3.10.1 п.2 (КонсультантПлюс) | подтв. |
| grants | `support` | div/p (текст/ссылка) | меры социальной поддержки | 9.0.0 п.3 | подтв. |
| grants | `hostelInfo`, `interInfo`, `hostelNum`, `hostelNumOvz`, `interNum`, `interNumOvz` | td/div | дублируют сведения об общежитии из objects | 9.0.0 пп.4–9 | подтв. (в 9.0.0); после ред. 920 пп. «в–д» п.17 приказа утратили силу → в 10.0.0, вероятно, убраны |
| grants | `localActObSt` | a | плата за проживание в общежитии | 9.0.0 п.10 | подтв. (9.0.0), см. выше |

Убрано в 9.0.0 по сравнению с 8.x: главный тег-обёртка `grant` с детьми `typeGrant`, `localGrant`, `federalGrant`, `localActObSt`;
`localAct` (ЛНА о стипендиях) — отменён (db-nica.ru/blog). `graduateJob` переехал в education (с 8.x).
**Рекомендация для grants:** `<div itemprop="grant">Выплата стипендий не предусмотрена</div>`,
`<div itemprop="support">Меры социальной поддержки не предусмотрены</div>` + блок общежития как в objects (нули) — безопасно для 9.0.0 и 10.0.0.

### paid_edu — «Платные образовательные услуги» (табл. 3.11.1 v9.0.0)
| подраздел | itemprop | где ставится | что размечает | источник | уверенность |
|---|---|---|---|---|---|
| paid_edu | `paidEdu` | **a** | документ о порядке оказания платных образовательных услуг (эл. док. с ЭП) | 9.0.0 табл. 3.11.1 п.1 + пример | подтв. |
| paid_edu | `paidDog` | **a** | образец договора об оказании платных образовательных услуг | 9.0.0 п.2 | подтв. |
| paid_edu | `paidSt` | **a** | документ об утверждении стоимости обучения по каждой образовательной программе | 9.0.0 п.3 | подтв. |
| paid_edu | `paidParents` | a / span | плата за присмотр и уход (ДО, интернат, ГПД) — **нам не нужно**, но можно `<span itemprop="paidParents">Отсутствует</span>` | 9.0.0 п.4 (со *) | подтв. |

В 8.x был только `paidEdu` (обёртка). `paidDog`, `paidSt`, `paidParents` — новые с 8.x/9.0.0 (под новый п.14 Приказа 1493).
Таблицу цен по программам на странице можно выводить без itemprop (иначе только `paidSt` на документе).

### budget — «Финансово-хозяйственная деятельность» (табл. 3.12.1 v9.0.0)
Источники: (A) словарь aplicon-ru/edu-framework `standards/sveden/vocab/base.yaml`, «выверен против МР v9.0.0» (2026-06);
(B) «Актуализированные МР» (rulaws.ru, старая версия); (C) itemtype `Volume` и `FinRec` из старой схемы (nivasposad.ru/sveden/budget —
отдельные группы); (D) МР 3.3.0 (2019, mpei.ru): `finPost`, `finRas`. Полный текст табл. 3.12.1 сам не прочитал.
| подраздел | itemprop | где ставится | что размечает | источник | уверенность |
|---|---|---|---|---|---|
| budget | `volume` | **tr** (главный) | строка «объём образовательной деятельности за год» | A, B, C | вероятно (2+ источника) |
| budget | `finYear` | td | финансовый год | A | вероятно |
| budget | `finBFVolume` | td | объём за счёт федерального бюджета (тыс. руб.) | A, B | вероятно |
| budget | `finBRVolume` | td | … бюджетов субъектов РФ | A, B | вероятно |
| budget | `finBMVolume` | td | … местных бюджетов | A, B | вероятно |
| budget | `finPVolume` | td | … по договорам об образовании за счёт физ. и (или) юр. лиц | A, B | вероятно |
| budget | `finRec` | **tr** (главный) | строка «поступление и расходование средств по итогам года» | B, C (в A отдельной группы нет — finPost/finRas положены внутрь volume) | вероятно |
| budget | `finPost` | td | поступление финансовых и материальных средств | A, D | вероятно |
| budget | `finRas` | td | расходование финансовых и материальных средств | A, D | вероятно |
| budget | `finPlanDocLink` | **a** | план ФХД / бюджетная смета (эл. документ с ЭП) | A, B | вероятно |

**Рекомендация (покрывает обе трактовки):**
```html
<table><tr itemprop="volume"><td itemprop="finYear">2025</td><td itemprop="finBFVolume">0</td><td itemprop="finBRVolume">0</td>
  <td itemprop="finBMVolume">0</td><td itemprop="finPVolume">12 450,0</td></tr></table>
<table><tr itemprop="finRec"><td itemprop="finYear">2025</td><td itemprop="finPost">12 600,0</td><td itemprop="finRas">11 980,0</td></tr></table>
<a href="..." itemprop="finPlanDocLink">План финансово-хозяйственной деятельности на 2026 год</a>
```
Для АНО ДПО бюджета нет → «0» (Официальные разъяснения Рособрнадзора 11.11.2024: при нулевом объёме — «0»).
АНО не обязана иметь «план ФХД» как бюджетное учреждение — размещают «Смету доходов и расходов на 20__ год» (утв. директором) под `finPlanDocLink`.

### vacant — «Вакантные места для приёма (перевода) обучающихся» (табл. 3.13.1 v9.0.0)
| подраздел | itemprop | где ставится | что размечает | источник | уверенность |
|---|---|---|---|---|---|
| vacant | `vacant` | **tr** (главный) | строка по образовательной программе | A, B, МР 3.3.0 | вероятно (стабилен с 2019) |
| vacant | `eduCode` | td | код (ПО — код профессии ОКПДТР; ДПО — «—») | A | вероятно |
| vacant | `eduName` | td | наименование профессии/программы | A | вероятно |
| vacant | `eduLevel` | td | уровень образования (ДПО / профессиональное обучение) | A | вероятно |
| vacant | `eduProf` | td | образовательная программа, направленность | A | вероятно |
| vacant | `eduCourse` | td | курс (для нас «—» / «1») | A | вероятно |
| vacant | `eduForm` | td | форма обучения | A | вероятно |
| vacant | `numberBFVacant` | td | вакантные места за счёт федерального бюджета | A, B | вероятно |
| vacant | `numberBRVacant` | td | … бюджетов субъектов РФ | A, B | вероятно |
| vacant | `numberBMVacant` | td | … местных бюджетов | A, B | вероятно |
| vacant | `numberPVacant` | td | по договорам за счёт физ./юр. лиц (именно **места**, не контингент) | A, B | вероятно |

Удалены (ранние версии): `nameProgVacant`, `specialVacant`, `bachelorVacant`, `specialityVacant`, `magistracyVacant`,
`postgraduateVacant`, `obrVacant`, `specVacant`, `naprVacant`, `profesVacant` — **не использовать**.
**⇒ В CONTRACT.md для vacant добавить td `eduProf` и `eduCourse`** (сейчас там eduCode, eduName, eduLevel, eduForm, number*Vacant).
Для ДПО по договорам часто пишут количество мест в группе (напр. 12–25) или «Не ограничено» — оба варианта встречаются;
Яндекс Практикум (АНО ДПО) пишет «бюджетная деятельность не ведётся» + ссылку на набор (yandex.ru/edtech/sveden/vacant).

### inter — «Международное сотрудничество» (табл. 3.14.1 v9.0.0)
| подраздел | itemprop | где ставится | что размечает | источник | уверенность |
|---|---|---|---|---|---|
| inter | `internationalDog` | **tr** (главный) | строка «договор с иностранной/международной организацией» | A (+ по памяти из 8.x) | вероятно (1 письменный источник) |
| inter | `stateName` | td | государство | A | вероятно |
| inter | `orgName` | td | наименование организации | A | вероятно |
| inter | `dogReg` | td | реквизиты договора (наименование, дата, номер, срок) | A | вероятно |

Ред. № 1353 добавила «и планируемых к заключению» договоров (п.18). Отдельного атрибута для планируемых в A нет — выводим их
в той же таблице/тексте. **Рекомендация:**
`<tr itemprop="internationalDog"><td itemprop="stateName">Отсутствует</td><td itemprop="orgName">Отсутствует</td><td itemprop="dogReg">Отсутствует</td></tr>`
+ текст «Договоры с иностранными и (или) международными организациями по вопросам образования и науки не заключались и не планируются».

### catering — «Организация питания в образовательной организации» (табл. 3.15.1 v9.0.0)
| подраздел | itemprop | где ставится | что размечает | источник | уверенность |
|---|---|---|---|---|---|
| catering | `meals` | **tr** (главный) | строка «объект питания» | A, МР 3.3.0, rulaws | вероятно (2+ источника) |
| catering | `objName`, `objAddress`, `objOvz` | td (внутри meals) | наименование / адрес / приспособленность для ОВЗ | A; db-nica: в 9.0.0 удалены площадь и кол-во мест | вероятно |
| catering | `health` | div/p или **a** | условия охраны здоровья обучающихся (в 9.0.0 — отдельный пункт, текст или ссылка) | A, db-nica blog | вероятно |

**Рекомендация (учебный центр без столовой):**
`<tr itemprop="meals"><td itemprop="objName">Отсутствует</td><td itemprop="objAddress">Отсутствует</td><td itemprop="objOvz">Отсутствует</td></tr>`
+ текст: «Питание обучающихся не организуется (краткосрочное обучение взрослых; в перерывах — зона отдыха с кулером)» (если правда);
`<div itemprop="health">Охрана здоровья обучающихся обеспечивается в соответствии со ст. 41 Федерального закона № 273-ФЗ: ...</div>`.

### education / eduStandarts — перепроверка (9.0.0 и 10.0.0, подтв.)
| подраздел | itemprop | где | что | уверенность |
|---|---|---|---|---|
| education | `eduAccred` (tr) → `eduCode`, `eduName`, `eduProf`, `eduLevel`, `eduForm`, `learningTerm`, `eduPred`, `eduPrac` (td) | tr/td | реализуемые уровни/программы, формы, сроки, предметы, практики | подтв. (3.5.1 п.1, пример 3.5.2) |
| education | `languageEl`, `eduChislenEl`, `eduPriemEl`, `eduPerevodEl` | **a** | языки; численность; результаты приёма; перевод/восстановление/отчисление (эл. документы) | подтв. |
| education | `eduOp` (tr) → `eduCode`, `eduName`, `eduLevel`, `eduProf`, `eduForm` (td) + `opMain`, `educationPlan`, `educationRpd`, `educationShedule`, `eduPr`, `methodology` (a) | tr/td/a | образовательные программы (осн. и адаптированные объединены в eduOp с 9.0.0) | подтв. |
| education | `eduNir` (tr) → `eduCode`, `eduName`, `perechenNir`, `eduProf`, `eduLevel`, `napravNir`, `resultNir`, `baseNir` | tr/td | научная деятельность (для ДПО — обязательно указать; при отсутствии «отсутствует») | подтв. (`napravNir` есть в 10.0.0) |
| education | `graduateJob` (tr) → `eduCode`, `eduName`, `eduProf`, `v1`, `t1` | tr/td | трудоустройство (только СПО/ВО) | подтв. |
| education | `accreditationDocLink` | a / span | выписка из реестра аккредитации; для ДПО/ПО — `<span itemprop="accreditationDocLink">Отсутствует</span>` | подтв. (3.5.1 п.9 в 10.0.0) |
| eduStandarts | `eduFedDoc`, `eduStandartDoc`, `eduFedTreb`, `eduStandartTreb` | **a** (или span «Отсутствует») | ФГОС; собственные стандарты; ФГТ; самостоятельно устанавливаемые требования | подтв. |

**Правка к REQUIREMENTS_1493.md / CONTRACT.md:** `accreditationDocLink` в 9.0.0/10.0.0 — в **education**, а не только в common
(с 01.09.2025 сведения об аккредитации — в подразделе «Образование»). В eduNir добавить `napravNir`. Для ДПО/ПО:
`eduOp` с `eduCode` = «—» (ДПО) или код ОКПДТР (ПО). Для `eduAccred` у ДПО — `learningTerm` = срок освоения (часы/дни).

## 3. Что изменилось относительно рекомендаций 2020–2022 (сводка)
| Было (≤8.x) | Стало (9.0.0 / 10.0.0) | уверенность |
|---|---|---|
| обёртка `mto` (3.3.0) | нет обёртки, отдельные атрибуты | подтв. |
| `purposeCabOvz`, `purposePracOvz`, `purposeLibrOvz`, `purposeSportOvz` | `ovzCab`, `ovzPrac`, `objOvz` внутри строк | подтв. |
| библиотека/спорт: `objSq` (площадь), `objCnt` (кол-во мест) | удалены — только `objName`, `objAddress`, `objOvz` | подтв. (таблица 9.0.0 + db-nica) |
| `purposeEios`, `infoEios` → `eoisOwn`, `eoisSide`, `bdec`, `purposeInternet`, `purposeEbs` | удалены | подтв. (нет в 9.0.0; cposo 8.9.1: удалены eoisOwn/eoisSide/bdec) |
| `meals`, `health` в МТО | вынесены в catering (новый подраздел с ред. 1493) | подтв./вероятно |
| grants: `grant`(обёртка) → `typeGrant`, `localGrant`, `federalGrant`, `localAct` | `grant`, `support` — текст | подтв. |
| `graduateJob` в grants | в education | подтв. |
| paid_edu: `paidEdu` | `paidEdu`, `paidDog`, `paidSt`, `paidParents` | подтв. |
| `accreditationDocLink` в common | в education (с 01.09.2025) | подтв. |
| `copy` в каждой таблице | в 10.0.0 исключён из проверяемых пунктов | подтв. (новость ФРЦ ДС + таблицы 10.0.0) |
| budget: `finSred` → `finPost`, `finRas` (3.3.0) | `volume` → `finYear`, `fin*Volume`; `finRec` → `finPost`, `finRas`; `finPlanDocLink` | вероятно |
| vacant: `obrVacant`/`bachelorVacant`… | `vacant` → `eduCode`, `eduName`, `eduLevel`, `eduProf`, `eduCourse`, `eduForm`, `number*Vacant` | вероятно |
| catering: `meals` → `objName`, `objAddress`, `objSq`, `objCnt`, `objOvz`; `health` — главный тег | `meals` → `objName`, `objAddress`, `objOvz`; `health` — одиночный | вероятно (db-nica + A) |

## Источники
- Методические рекомендации 9.0.0 (2025), PDF: https://db-nica.ru/documents/regulations/sveden/metodicheskie-rekomendaczii-2025.pdf
- КонсультантПлюс, 9.0.0: п.3.9 https://www.consultant.ru/document/cons_doc_LAW_177135/7a07b4886364b0616a351740448b9b91cc5dbf16/ ;
  п.3.10 https://www.consultant.ru/document/cons_doc_LAW_177135/2085c3f36fed3f2d5750516e8403067a95d6dfd9/ ;
  п.3.11 https://www.consultant.ru/document/cons_doc_LAW_177135/1b8739dbb75d31ebe5d3f78a97503be462894b00/ ;
  п.3.12 (только заголовок) https://www.consultant.ru/document/cons_doc_LAW_177135/a7d9208de0de0ae37b58dd811ccbb8c44ed5729e/
- Версия 10.0.0: https://www.frcds.ru/news-14-09-2026/ ; https://www.frcds.ru/wp-content/uploads/2026/09/metod-rek-minobr-ver-10.0.0.pdf ;
  https://pravo.ppt.ru/metodicheskiye-rekomendatsii/353943
- Обзор изменений 9.0.0: https://db-nica.ru/blog/metodicheskie-rekomendacii-2025-chto-izmenilosy-v-trebovaniyah-k-saytu-obrazovatelynoy-org
- Версия 8.9.1 (раздел «Изменения»): https://www.cposo.ru/images/2025/mr_site2.pdf
- «Актуализированные» (старая версия, budget/vacant): https://rulaws.ru/acts/Aktualizirovannye-metodicheskie-rekomendatsii-predstavleniya-informatsii-ob-obrazovatelnoy-organizatsii-/
- Версия 3.3.0 (2019): https://mpei.ru/feedback/Documents/Recommendations2019.pdf
- (A) Словарь sveden, выверенный по 9.0.0: https://github.com/aplicon-ru/edu-framework/tree/main/standards/sveden
  (raw: https://raw.githubusercontent.com/aplicon-ru/edu-framework/main/standards/sveden/vocab/base.yaml) — в нём же: `copy` «срок
  требования — до 01.09.2025 (стр. 19 МР 9.0.0)».
- Официальные разъяснения Рособрнадзора от 11.11.2024 (что писать при отсутствии: «не предусмотрено» / «0»):
  https://www.garant.ru/products/ipo/prime/doc/410649332/
- Яндекс Практикум (АНО ДПО), пример vacant для ДПО: https://yandex.ru/edtech/sveden/vacant
