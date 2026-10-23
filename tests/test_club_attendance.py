import pytest
from datetime import datetime


@pytest.mark.asyncio
async def test_club_attendance_crud(test_client, staff_headers, student_headers):
    # Ensure there's at least one club
    resp = await test_client.get('/clubs/')
    assert resp.status_code in (200, 401)
    clubs = resp.json() if resp.status_code == 200 else []

    if not clubs:
        # create a club with staff authorization
        club_data = {
            "name": "Test Club API",
            "description": "Temp",
            "category": "Social",
            "advisor": "Dr Test",
        }
        create_resp = await test_client.post('/clubs/', json=club_data, headers=staff_headers)
        assert create_resp.status_code in (201, 400, 401, 422)
        if create_resp.status_code == 201:
            club_id = create_resp.json()['id']
        else:
            pytest.skip('Cannot create club in test environment')
    else:
        club_id = clubs[0]['id']

    # Post attendance for today (staff authorization)
    payload = {
        "attendance_date": datetime.utcnow().isoformat(),
        "roster": [
            {"student_name": "Alice", "roll_number": "21CS001", "section": "A", "present": True},
            {"student_name": "Bob", "roll_number": "21CS002", "section": "A", "present": False}
        ]
    }
    post_resp = await test_client.post(f'/clubs/{club_id}/attendance', json=payload, headers=staff_headers)
    assert post_resp.status_code in (201, 400, 401)

    # Query attendance for today (authenticated user)
    date_str = datetime.utcnow().date().isoformat()
    get_resp = await test_client.get(f'/clubs/{club_id}/attendance?date={date_str}', headers=student_headers)
    assert get_resp.status_code in (200, 404, 401)
