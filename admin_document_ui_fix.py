import html
import re

from flask import request
from flask_login import current_user
from flask_wtf.csrf import generate_csrf

import admin_bulk_document_delete_manager  # noqa: F401

app = admin_bulk_document_delete_manager.app
ADMIN_ROLE = "관리자"

# Disable the former client-side-only injector. Bulk delete routes remain registered.
for _func in list(app.after_request_funcs.get(None, [])):
    if getattr(_func, "__name__", "") == "inject_admin_bulk_document_delete":
        app.after_request_funcs[None].remove(_func)


def _delete_icon_form(kind, document_id, csrf_token):
    if kind == "meeting":
        action = f"/document-control/meetings/{document_id}/delete"
        message = "이 일일회의 문서를 삭제하시겠습니까? 연결된 원본 업무는 삭제되지 않습니다."
    else:
        action = f"/document-control/journals/{document_id}/delete"
        message = "이 업무일지 문서를 삭제하시겠습니까? 연결된 원본 업무는 삭제되지 않습니다."
    return (
        f'<form method="post" action="{action}" class="document-row-delete-form" '
        f'onsubmit="return confirm(\'{html.escape(message, quote=True)}\');">'
        f'<input type="hidden" name="csrf_token" value="{html.escape(csrf_token, quote=True)}">'
        '<button class="button danger small" type="submit" title="삭제" aria-label="삭제" '
        'style="min-width:36px;padding:7px 9px">'
        '<svg class="button-icon" viewBox="0 0 24 24" aria-hidden="true">'
        '<path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5M14 11v5"/></svg>'
        '</button></form>'
    )


def _bulk_bar(kind, csrf_token):
    if kind == "meeting":
        form_id = "adminMeetingBulkDeleteForm"
        action = "/document-control/meetings/bulk-delete"
        noun = "일일회의 문서"
    else:
        form_id = "adminJournalBulkDeleteForm"
        action = "/document-control/journals/bulk-delete"
        noun = "업무일지 문서"
    return (
        '<div class="document-admin-bulk-actions" style="display:flex;justify-content:flex-end;align-items:center;gap:10px;margin:0 0 12px">'
        f'<form id="{form_id}" method="post" action="{action}" '
        f'onsubmit="return confirm(\'선택한 {noun}를 삭제하시겠습니까? 연결된 원본 업무는 삭제되지 않습니다.\');">'
        f'<input type="hidden" name="csrf_token" value="{html.escape(csrf_token, quote=True)}">'
        '<span class="permission-muted" data-admin-document-selected-label>선택 0건</span> '
        '<button class="button danger small" type="submit" data-admin-document-bulk-delete disabled>'
        '<svg class="button-icon" viewBox="0 0 24 24" aria-hidden="true">'
        '<path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13M10 11v5M14 11v5"/></svg>'
        '<span>선택 문서 삭제</span></button></form></div>'
    )


def _selection_script():
    return """<script>
(function(){
  function bind(){
    var table=document.querySelector('table[data-admin-document-table]');
    if(!table||table.dataset.adminDeleteBound==='true')return;
    table.dataset.adminDeleteBound='true';
    var all=table.querySelector('[data-admin-document-select-all]');
    var checks=Array.from(table.querySelectorAll('[data-admin-document-check]'));
    var button=document.querySelector('[data-admin-document-bulk-delete]');
    var label=document.querySelector('[data-admin-document-selected-label]');
    function update(){
      var selected=checks.filter(function(c){return c.checked;});
      if(button){button.disabled=!selected.length;var s=button.querySelector('span');if(s)s.textContent=selected.length?'선택 '+selected.length+'건 삭제':'선택 문서 삭제';}
      if(label)label.textContent='선택 '+selected.length+'건';
      if(all){all.checked=checks.length>0&&selected.length===checks.length;all.indeterminate=selected.length>0&&selected.length<checks.length;}
    }
    if(all)all.addEventListener('change',function(){checks.forEach(function(c){c.checked=all.checked;});update();});
    checks.forEach(function(c){c.addEventListener('change',update);});
    update();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',bind);else bind();
})();
</script>"""


def _inject_board(page, kind, csrf_token):
    if kind == "meeting":
        table_html = '<table class="meeting-board-table">'
        table_new = '<table class="meeting-board-table" data-admin-document-table="meeting">'
        form_id = "adminMeetingBulkDeleteForm"
        preview_pattern = re.compile(r'<tr>(?P<body>.*?data-meeting-preview="/meetings/(?P<id>\d+)/preview".*?</td>)</tr>', re.DOTALL)
        end_header = '<th>작성일</th></tr></thead>'
        end_header_new = '<th>작성일</th><th style="width:60px">관리</th></tr></thead>'
        empty_old = 'colspan="9">저장된 일일회의 문서가 없습니다.'
        empty_new = 'colspan="11">저장된 일일회의 문서가 없습니다.'
        aria = "일일회의 문서"
    else:
        table_html = '<table class="meeting-board-table journal-board-table">'
        table_new = '<table class="meeting-board-table journal-board-table" data-admin-document-table="journal">'
        form_id = "adminJournalBulkDeleteForm"
        preview_pattern = re.compile(r'<tr>(?P<body>.*?data-journal-preview="/journals/(?P<id>\d+)/preview".*?</td>)</tr>', re.DOTALL)
        end_header = '<th>등록일</th></tr></thead>'
        end_header_new = '<th>등록일</th><th style="width:60px">관리</th></tr></thead>'
        empty_old = 'colspan="8">저장된 업무일지가 없습니다.'
        empty_new = 'colspan="10">저장된 업무일지가 없습니다.'
        aria = "업무일지 문서"

    if table_html not in page or 'data-admin-document-table=' in page:
        return page
    page = page.replace(table_html, _bulk_bar(kind, csrf_token) + table_new, 1)
    page = page.replace(
        '<thead><tr><th>No.</th>',
        f'<thead><tr><th style="width:44px"><input type="checkbox" data-admin-document-select-all aria-label="{aria} 전체 선택" title="전체 선택"></th><th>No.</th>',
        1,
    )
    page = page.replace(end_header, end_header_new, 1)

    def replace_row(match):
        document_id = match.group("id")
        select_cell = (
            f'<td><input type="checkbox" name="document_ids" value="{document_id}" form="{form_id}" '
            f'data-admin-document-check aria-label="{aria} 선택"></td>'
        )
        return f'<tr>{select_cell}{match.group("body")}<td>{_delete_icon_form(kind, document_id, csrf_token)}</td></tr>'

    page = preview_pattern.sub(replace_row, page)
    page = page.replace(empty_old, empty_new, 1)
    return page


@app.after_request
def render_admin_document_delete_controls(response):
    if (
        response.mimetype == "text/html"
        and response.status_code < 400
        and current_user.is_authenticated
        and current_user.role.name == ADMIN_ROLE
        and request.path in {"/meetings", "/journals"}
    ):
        page = response.get_data(as_text=True)
        page = page.replace('<script src="/static/admin_bulk_document_delete.js?v=20260905-admin-bulk-delete" defer></script>', '')
        kind = "meeting" if request.path == "/meetings" else "journal"
        page = _inject_board(page, kind, generate_csrf())
        if 'data-admin-document-table=' in page and '</body>' in page:
            page = page.replace('</body>', _selection_script() + '</body>')
        response.set_data(page)
        response.headers.pop("Content-Length", None)
    return response
