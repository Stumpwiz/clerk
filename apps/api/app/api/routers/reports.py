"""API router for report generation"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional

from app.db.base import get_db
from app.security.auth import get_current_user, ClerkUser

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/vacancy")
def vacancy_report(
    db: Session = Depends(get_db),
    current_user: ClerkUser = Depends(get_current_user)
):
    """Generate vacancy report - offices without current assignments"""
    query = text(
        """
            SELECT 
                body.name as body_name,
                office.title as office_title,
                office.office_precedence
            FROM office
            JOIN body ON body.body_id = office.office_body_id
            LEFT JOIN term ON term.termofficeid = office.office_id 
                AND (term.end IS NULL OR term.end > date('now'))
            WHERE term.termpersonid IS NULL
            ORDER BY body.body_precedence, office.office_precedence
        """
    )
    result = db.execute(query)
    vacancies = [dict(row._mapping) for row in result]
    return {"vacancies": vacancies, "count": len(vacancies)}


@router.get("/expiring-terms")
def expiring_terms_report(
    days: int = Query(90, description="Number of days to look ahead"),
    db: Session = Depends(get_db),
    current_user: ClerkUser = Depends(get_current_user)
):
    """Generate expiring terms report"""
    query = text(
        """
            SELECT 
                person.first,
                person.last,
                person.email,
                body.name as body_name,
                office.title as office_title,
                term.end as term_end_date
            FROM term
            JOIN person ON person.personid = term.termpersonid
            JOIN office ON office.office_id = term.termofficeid
            JOIN body ON body.body_id = office.office_body_id
            WHERE term.end IS NOT NULL 
                AND term.end <= date('now', '+' || :days || ' days')
                AND term.end >= date('now')
            ORDER BY term.end, body.body_precedence
        """
    )
    result = db.execute(query, {"days": days})
    expiring = [dict(row._mapping) for row in result]
    return {"expiring_terms": expiring, "count": len(expiring), "days_ahead": days}


@router.get("/full-roster")
def full_roster_report(
    db: Session = Depends(get_db),
    current_user: ClerkUser = Depends(get_current_user)
):
    """Generate full roster from report_record view"""
    query = text("SELECT * FROM report_record")
    result = db.execute(query)
    roster = [dict(row._mapping) for row in result]
    return {"roster": roster, "count": len(roster)}
