# Go-live checklist – assumptions and what I need from you

Run `python scripts/check_config.py` any time: it lists the blocking items below that are still unfinished.

## A. What I need from you before going live

### Must have
| # | Item | Why / where it goes |
|---|---|---|
| 1 | **Logo file** – PNG or SVG, ideally transparent background, at least 512 × 512 px | The file you sent is only about 150 px wide, so it looks soft in the header and in WhatsApp/Google share previews. Replace `public/img/logo-original.jpg`. |
| 2 | **Real contact details** – phone, WhatsApp (with country code), public email, **the inbox that should receive enquiry alerts**, full address, office hours | *Admin → Site settings*. The samples are placeholders (`hello@prashitutorial.example`, “Your branch address…”). |
| 3 | **Email (SMTP) account** | Without it no enquiry alert or “forgot password” email is sent. See README Part 2. Run `python scripts/test_email.py you@example.com`. |
| 4 | **Domain name and hosting decision** (and who will look after the server) | README Part 4. Needs Python 3.12+, a persistent disk, HTTPS. |
| 5 | **Your real courses and fee structure** – names, class levels, exams, subjects, duration, fees, instalment plans | *Admin → Courses*. And decide: **should fees be public?** (currently hidden, “Contact us”.) |
| 6 | **Real batches** – names, timings, start dates, seats, open/full status | *Admin → Batches*. |
| 7 | **Faculty** – names, qualifications, short bios, photos (with their permission) | *Admin → Faculty*. |
| 8 | **Privacy Policy and Terms** reviewed or written for you (consent wording, data retention period, grievance/contact person, fee-refund rules) | *Admin → Page text → Privacy Policy / Terms*. The Privacy Policy is a draft; Terms is a placeholder. |
| 9 | **Read and confirm the page wording** (section C) | *Admin → Page text*. |

### Good to have
* Real **results**, rank holders and **testimonials** – with the families’ consent.
* **FAQs** parents really ask; admission **steps, eligibility and dates**.
* Your **Google Maps embed link** and **social media links**.
* **About-page story**: founding year, mission, journey, campus facilities (enter under Page text), and genuine student/faculty numbers for the home-page counters (Site settings).
* Your **existing students** as a spreadsheet (see Admin Guide → Import many students). Check the **fee receipt** layout (Admin → a student → click a receipt number) and tell me what to change; add your registration/GST line under Page text → Footer & receipts.
* Who gets **Admin** vs **Staff** logins, and a **second admin** for safety.
* A place for **off-server backups** (another computer / cloud drive).

## B. Assumptions I made – tell me if any is wrong
* One branch, English only, amounts in ₹, Indian time zone (`Asia/Kolkata`).
* **Fees are private by default.** Phone numbers and fees are never public.
* **One login per student; parents share it** (no separate parent accounts). Parent phone/email are stored on the student for contact and password reset.
* **Fees are recorded manually** by the admin (no online payment). Balance = fee − discount − payments, always calculated.
* Roles: **admin** (everything) and **staff** (enquiries, students, records, attendance, doubts). More roles can be added later.
* New content starts as a **draft/hidden**; tutorial records start **hidden from students**.
* Student login name is the admission number (`PT` + year + 4 digits, e.g. `PT260001`); temporary passwords are shown to the admin once.
* Passwords: at least 10 characters. 5 wrong tries locks an account 15 minutes. Signed out after 8 idle hours.
* Public forms: privacy-consent tick is mandatory, 8 submissions per 10 minutes per visitor.
* Uploads: pictures 5 MB (JPG/PNG/GIF/WebP), documents 20 MB (PDF, Word, PowerPoint, Excel, text, ZIP, JPG, PNG).
* Enquiry statuses: New / Contacted / Demo booked / Enrolled / Closed. Attendance: Present / Absent / Late / Excused.
* The WhatsApp button is a link to open WhatsApp – the site does not send WhatsApp or SMS messages itself.
* SQLite on a single server is enough for your size. Moving to PostgreSQL later is possible but not built.
* No automatic data deletion; keeping and deleting student records is a manual decision.
* “Preview before publishing” is available for **courses and articles**; other content uses draft → publish.
* The admin “Download data” gives one Excel file per database table (23), and the **Data export never includes passwords**.

## C. Wording that came with the sample – now editable by you
All public wording is edited in **Admin → Settings → Page text** (no files). The sample text includes **factual claims** (batches of 25, same-day doubts, monthly parent reports, “CCTV, women staff on every floor and verified pickup”, “Admissions open · 2026–27”, the entrance-test sentence). **Please read each section, correct anything that is not true for Prashi Tutorial, and click Save page text.**

`python scripts/check_config.py` stays red until you have saved that screen once **and** replaced the draft **Privacy Policy** and placeholder **Terms**. (Have a lawyer review those two, and add your fee/refund rules to the Terms.)

Still in the template files (rarely changed): the section headings “Popular courses”, “Meet the faculty”, “What students say”, “Upcoming batches”, “Questions parents ask”, and the floating hero cards. Tell me if you want any of those editable too.

## D. Final pre-launch routine (about 30 minutes)
1. `python scripts/check_config.py` → no “MUST FIX”.
2. Sign in on a **phone** and a **laptop**; click through every admin menu, add and edit one item of each kind.
3. Open the public site on a phone: Home, a course, Admissions form (submit a test enquiry, confirm the email arrives and it shows in **Enquiries & admissions**).
4. Create a test student, enrol them, record a payment, release a note, sign in as that student and confirm they see only that.
5. Run `python scripts/backup.py` and copy the backup somewhere safe.
6. Delete the test student/enquiry. Create a second admin login.
7. Submit the site to Google Search Console using `https://yourdomain/sitemap.xml`.
