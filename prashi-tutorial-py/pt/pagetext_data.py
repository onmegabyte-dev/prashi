# Generated from the original page-text tables (wording is unchanged). Edit wording from the admin "Page text" screen, not here.
DEFAULTS = {'hero_tag': 'Admissions open · 2026–27',
 'hero_line1': 'Learn Today.',
 'hero_line2': 'Lead Tomorrow.',
 'hero_text': 'Prashi Tutorial coaches Classes 6–12 for boards, JEE, NEET and Olympiads with small batches, weekly tests and same-day '
              'doubt support.',
 'why_title': 'Why families choose Prashi Tutorial',
 'why_items': 'Small batches | 25 students at most, so no one gets lost.\n'
              'Same-day doubts | Ask on chat or in the clinic; get an answer before you sleep.\n'
              'Parent reports | A clear monthly report on marks, attendance and effort.\n'
              'Safe campus | CCTV, women staff on every floor and verified pickup.',
 'how_title': 'How we teach',
 'how_items': 'Learn the idea | Short concept sessions with diagrams and live examples.\n'
              'Practise daily | Graded problem sets from basic to exam level.\n'
              'Test weekly | Timed mocks with a rank and topic-wise breakdown.\n'
              'Fix and repeat | Error logs and doubt clinics close each gap.',
 'cta_title': 'Your next rank starts with one free class.',
 'cta_text': 'Meet a counsellor, sit a demo class, then decide.',
 'cta_button': 'Book a Free Counselling Session',
 'about_intro': 'Coaching that feels like mentoring.',
 'about_mission': 'Make excellent teaching reachable for every serious student.',
 'about_vision': 'A generation of curious, confident learners who lead in their fields.',
 'about_values': 'Honesty, effort, curiosity and care for each student.',
 'about_journey': 'Day one | Started with a small group of students in one room.\n'
                  'Growing | Our first top-rank results.\n'
                  'Online | Launched live online batches.\n'
                  'Today | Thousands of students taught by a dedicated faculty.',
 'about_campus': 'Air-conditioned classrooms, a library, a science lab, a doubt clinic and a quiet study hall.',
 'admissions_intro': 'Four simple steps from enquiry to first class.',
 'admissions_steps': 'Enquire | Fill the form or call us.\n'
                     'Counselling | Meet a counsellor and attend a demo class.\n'
                     'Assessment | A short test to place your child in the right batch.\n'
                     'Enrol | Pay the first instalment and receive your timetable.',
 'admissions_eligibility': 'Open to students in Classes 6–12. Class 11–12 courses need an entrance test.',
 'admissions_dates': 'Dates are announced in the notices and by our counsellor.',
 'footer_blurb': 'Small batches, expert teachers and honest guidance for Classes 6–12 and competitive exams.',
 'footer_note': '',
 'receipt_reg_line': '',
 'receipt_note': 'This is a computer-generated receipt and does not need a signature. Fees once paid are subject to the institute’s refund '
                 'policy.',
 'privacy_html': '<p><b>Draft for review.</b> This is a plain-language starting point. Please have it checked against the laws that apply '
                 'to you (for India, the Digital Personal Data Protection Act, 2023) before going live, then delete this paragraph.</p>\n'
                 '<h2>What we collect</h2><p>When you fill a form we collect the details you type in, such as name, phone, email, class '
                 'and course interest. For enrolled students we also keep parent contact details, attendance, test scores, remarks and fee '
                 'records.</p>\n'
                 '<h2>Why we collect it</h2><p>To reply to your enquiry, arrange counselling, run your classes, and keep parents informed. '
                 'We do not sell your information.</p>\n'
                 '<h2>Who can see it</h2><p>Only authorised {{site_name}} staff. Students can see only their own records. Phone numbers '
                 'and fees are never shown on the public website.</p>\n'
                 '<h2>How we protect it</h2><p>Passwords are stored in scrambled (hashed) form. Connections use HTTPS. Access to staff '
                 'pages is checked on our server.</p>\n'
                 '<h2>How long we keep it</h2><p>Enquiries are kept for up to 2 years. Student records are kept while enrolled and for a '
                 'period afterwards for results and fee records.</p>\n'
                 '<h2>Your choices</h2><p>You can ask us to show, correct or delete your information by writing to <a '
                 'href="mailto:{{email}}">{{email}}</a>.</p>',
 'terms_html': '<p><b>Placeholder.</b> Replace this page with your real terms: fee and refund policy, batch transfer rules, attendance '
               'expectations and conduct, then delete this line.</p>'}

GROUPS = [{'id': 'home',
  'label': 'Home page',
  'where': 'The big banner at the top of the home page, then “Why families choose us”, “How we teach” and the call-to-action box.',
  'fields': [{'k': 'hero_tag',
              'l': 'Small label above the heading',
              't': 'text',
              'max': 80,
              'help': 'Example: Admissions open · 2026–27. Leave empty to hide it.'},
             {'k': 'hero_line1',
              'l': 'Main heading – first part',
              't': 'text',
              'max': 60,
              'req': 1,
              'help': 'Shown in plain text. Example: Learn Today.'},
             {'k': 'hero_line2',
              'l': 'Main heading – coloured part',
              't': 'text',
              'max': 60,
              'help': 'Shown in the blue-purple gradient after the first part. Example: Lead Tomorrow. Can be empty.'},
             {'k': 'hero_text',
              'l': 'Sentence under the heading',
              't': 'textarea',
              'rows': 3,
              'max': 400,
              'req': 1,
              'help': 'Also used as the home page description in Google results.'},
             {'k': 'why_title', 'l': '“Why families choose us” – heading', 't': 'text', 'max': 100},
             {'k': 'why_items',
              'l': '“Why families choose us” – items',
              't': 'textarea',
              'rows': 6,
              'max': 2500,
              'list': 1,
              'help': 'One item per line, written as: Title | Description (a vertical bar “|” separates the two). Up to 12 lines. Only '
                      'write claims that are true for your institute. Leave empty to hide the whole section.'},
             {'k': 'how_title', 'l': '“How we teach” – heading', 't': 'text', 'max': 100},
             {'k': 'how_items',
              'l': '“How we teach” – steps',
              't': 'textarea',
              'rows': 6,
              'max': 2500,
              'list': 1,
              'help': 'One item per line, written as: Title | Description (a vertical bar “|” separates the two). Up to 12 lines. Leave '
                      'empty to hide the section.'},
             {'k': 'cta_title', 'l': 'Call-to-action box – heading', 't': 'text', 'max': 120},
             {'k': 'cta_text', 'l': 'Call-to-action box – text', 't': 'text', 'max': 200},
             {'k': 'cta_button', 'l': 'Call-to-action box – button', 't': 'text', 'max': 60}]},
 {'id': 'about',
  'label': 'About page',
  'where': 'The About page.',
  'fields': [{'k': 'about_intro', 'l': 'Line under the page title', 't': 'text', 'max': 200},
             {'k': 'about_mission', 'l': 'Mission', 't': 'textarea', 'rows': 3, 'max': 600},
             {'k': 'about_vision', 'l': 'Vision', 't': 'textarea', 'rows': 3, 'max': 600},
             {'k': 'about_values', 'l': 'Values', 't': 'textarea', 'rows': 3, 'max': 600},
             {'k': 'about_journey',
              'l': 'Our journey (timeline)',
              't': 'textarea',
              'rows': 6,
              'max': 2500,
              'list': 1,
              'help': 'One milestone per line: Year or label | What happened. Example: 2011 | Started with 40 students in one room.'},
             {'k': 'about_campus', 'l': 'Campus', 't': 'textarea', 'rows': 3, 'max': 800}]},
 {'id': 'admissions',
  'label': 'Admissions page',
  'where': 'The Admissions page (above the forms).',
  'fields': [{'k': 'admissions_intro', 'l': 'Line under the page title', 't': 'text', 'max': 200},
             {'k': 'admissions_steps',
              'l': 'Admission steps',
              't': 'textarea',
              'rows': 6,
              'max': 2000,
              'list': 1,
              'help': 'One item per line, written as: Title | Description (a vertical bar “|” separates the two). Up to 12 lines.'},
             {'k': 'admissions_eligibility', 'l': 'Eligibility', 't': 'textarea', 'rows': 3, 'max': 600},
             {'k': 'admissions_dates',
              'l': 'Important dates',
              't': 'textarea',
              'rows': 3,
              'max': 600,
              'help': 'Example: Registration closes 25 Oct 2026 · Entrance test 1 Nov 2026 · Classes begin 8 Nov 2026.'}]},
 {'id': 'footer',
  'label': 'Footer & receipts',
  'where': 'The bottom of every page, and the printed fee receipts.',
  'fields': [{'k': 'footer_blurb', 'l': 'Footer – short description', 't': 'textarea', 'rows': 2, 'max': 300},
             {'k': 'footer_note',
              'l': 'Footer – extra note after the copyright',
              't': 'text',
              'max': 150,
              'help': 'Optional. Example: Registered under the Societies Act, No. 123.'},
             {'k': 'receipt_reg_line',
              'l': 'Receipt – registration / GST line',
              't': 'text',
              'max': 150,
              'help': 'Printed under your address on fee receipts. Example: Reg. No. 123/2015 · GSTIN 21ABCDE1234F1Z5. Leave empty if not '
                      'needed.'},
             {'k': 'receipt_note', 'l': 'Receipt – note at the bottom', 't': 'textarea', 'rows': 2, 'max': 400}]},
 {'id': 'privacy',
  'label': 'Privacy Policy',
  'where': 'The Privacy Policy page (/privacy).',
  'fields': [{'k': 'privacy_html',
              'l': 'Privacy Policy text',
              't': 'richtext',
              'max': 30000,
              'help': 'You can use {{site_name}}, {{email}}, {{phone}} and {{address}}; they are filled in from Site settings. Have a '
                      'lawyer check it before going live.'}]},
 {'id': 'terms',
  'label': 'Terms & Conditions',
  'where': 'The Terms page (/terms).',
  'fields': [{'k': 'terms_html',
              'l': 'Terms & Conditions text',
              't': 'richtext',
              'max': 30000,
              'help': 'You can use {{site_name}}, {{email}}, {{phone}} and {{address}}; they are filled in from Site settings.'}]}]
