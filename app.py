from sanic import Sanic
from sanic.response import json, html, redirect
from sanic_session import Session, InMemorySessionInterface
from models import *
from middlewares import requires_auth, before_login
import bcrypt
from datetime import datetime

app = Sanic("ParkingManagementSystem")
session = Session(app, interface=InMemorySessionInterface())

# 数据库相关
db_host = 'localhost'
db_port = '54321'
db_username = 'system'
db_password = '123123'
db_dbname = 'parking'


# 初始化数据库
@app.listener('before_server_start')
async def setup_db(app, loop):
    init(db_host, db_port, db_username, db_password, db_dbname)
    print('init finished!')


@app.route("/login", methods=["GET", "POST"])
@before_login()
async def login(request):
    if request.method == "GET":
        with open("templates/login.html", 'r', encoding='utf-8') as f:
            return html(f.read())
    elif request.method == "POST":
        data = request.json
        phone = data.get("phone")
        password = data.get("password")

        db_session = get_session()
        user = db_session.query(Personnel).filter(Personnel.phone == phone).first()

        if user and bcrypt.checkpw(password.encode(), user.password.encode()):
            request.ctx.session['userid'] = user.id
            return json({'msg': 'ok'})
        else:
            return json({"message": "Login failed"}, status=401)


@app.route("/register", methods=["POST", "GET"])
@before_login()
async def register(request):
    if request.method == "GET":
        with open("templates/register.html", 'r', encoding='utf-8') as f:
            return html(f.read())
    elif request.method == "POST":

        data = request.json
        username = data.get("username")
        password = data.get("password")
        department = data.get("department")
        room_num = data.get("room_num")
        phone = data.get("phone")

        db_session = get_session()
        hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        new_user = Personnel(
            name=username,
            password=hashed_password,
            department=department,
            room_num=room_num,
            phone=phone
        )

        db_session.add(new_user)
        db_session.commit()
        db_session.close()

        return json({'msg': 'ok'})


@app.route('/', methods=["GET"])
@requires_auth()
async def index(request):
    with open("templates/index.html", 'r', encoding='utf-8') as f:
        return html(f.read())


@app.route("/get_info", methods=["GET"])
@requires_auth()
async def get_vehicles(request):
    userid = request.ctx.session.get("userid")

    db_session = get_session()
    user = db_session.query(Personnel).filter(Personnel.id == userid).first()

    vehicles = (
        db_session.query(Vehicle, PersonnelParkingRelation)
        .join(PersonnelParkingRelation, Vehicle.plate == PersonnelParkingRelation.plate)
        .filter(PersonnelParkingRelation.personnel_id == user.id)
        .all()
    )

    vehicle_list = []

    for vehicle, relation in vehicles:
        last_in_record = db_session.query(VehicleAccessRecord).filter(VehicleAccessRecord.id == vehicle.last_in).first()
        last_in_time = last_in_record.timestamp.isoformat() if last_in_record else "N/A"
        last_in_area = db_session.query(ParkingArea).filter(
            ParkingArea.id == last_in_record.parking_id).first().name if last_in_record else "N/A"

        last_out_record = db_session.query(VehicleAccessRecord).filter(
            VehicleAccessRecord.id == vehicle.last_out).first()
        last_out_time = last_out_record.timestamp.isoformat() if last_out_record else "N/A"
        last_out_area = db_session.query(ParkingArea).filter(
            ParkingArea.id == last_out_record.parking_id).first().name if last_out_record else "N/A"

        veh_data = {
            "plate": vehicle.plate,
            "permissions": vehicle.permissions,
            "last entry": {
                "time": last_in_time,
                "parking area": last_in_area
            },
            "last time out": {
                "time": last_out_time,
                "parking area": last_out_area
            }
        }

        vehicle_list.append(veh_data)

    return json({"vehicles": vehicle_list})


@app.route("/vehicle/register", methods=["GET", "POST"])
@requires_auth()
async def vehicle_register(request):
    if request.method == "GET":
        with open("templates/vehicle_register.html", 'r', encoding='utf-8') as f:
            return html(f.read())
    elif request.method == "POST":
        data = request.json
        plate = data.get("plate")
        permissions = data.get("permissions")

        userid = request.ctx.session.get("userid")

        db_session = get_session()
        user = db_session.query(Personnel).filter(Personnel.id == userid).first()

        # 检查车牌是否已存在 逻辑更改： 不检查车牌存在，只进行车牌和人的绑定
        existing_vehicle = db_session.query(Vehicle).filter(Vehicle.plate == plate).first()
        if existing_vehicle:
            existing_vehicle.permissions = permissions
            db_session.commit()
        if not existing_vehicle:
            # 插入新车辆信息
            new_vehicle = Vehicle(plate=plate, permissions=permissions, paid=False)
            db_session.add(new_vehicle)
            db_session.commit()

        existing_relation = db_session.query(PersonnelParkingRelation).filter(
            PersonnelParkingRelation.plate == plate).first()
        if existing_relation:
            return json({'message': 'Vehicle registered by others'})

        # 插入人员车库关系
        new_relation = PersonnelParkingRelation(personnel_id=user.id, plate=plate)
        db_session.add(new_relation)
        db_session.commit()

        return json({"message": "Vehicle registered successfully"})


# 本来是应该由param设置停车场，然后根据停车场最新的出场记录获取车牌号
@app.route("/vehicle/pay", methods=["GET", "POST"])
async def vehicle_pay(request):
    if request.method == "GET":
        with open("templates/vehicle_pay.html", 'r', encoding='utf-8') as f:
            return html(f.read())
    elif request.method == "POST":
        data = request.json
        plate = data.get("plate")

        db_session = get_session()

        # 检查车辆是否存在
        vehicle = db_session.query(Vehicle).filter(Vehicle.plate == plate).first()
        if not vehicle:
            return json({"message": "Vehicle not found"}, status=404)

        if vehicle.paid:
            return json({"message": "Vehicle already paid"})

        # 查找车辆的最近一次进出记录
        last_in_record = db_session.query(VehicleAccessRecord).filter(
            VehicleAccessRecord.id == vehicle.last_in
        ).first()
        last_out_record = db_session.query(VehicleAccessRecord).filter(
            VehicleAccessRecord.id == vehicle.last_out
        ).first()

        if not last_in_record or not last_out_record:
            return json({"message": "Incomplete vehicle access records"}, status=400)

        # 计算时间间隔
        in_time = last_in_record.timestamp
        out_time = last_out_record.timestamp
        time_interval = out_time - in_time

        # 模拟付款过程并将其标记为已支付
        vehicle.paid = True
        db_session.commit()

        return json({
            "message": "Vehicle payment successful",
            "in_time": in_time.isoformat(),
            "out_time": out_time.isoformat(),
            "time_interval": str(time_interval)
        })


@app.route("/vehicle/update", methods=["GET", "POST"])
@requires_auth()
async def vehicle_update(request):
    if request.method == "GET":
        with open("templates/vehicle_update.html", 'r', encoding='utf-8') as f:
            return html(f.read())
    elif request.method == "POST":
        data = request.json
        plate = data.get("plate")
        new_permissions = data.get("permissions")

        userid = request.ctx.session.get("userid")

        db_session = get_session()
        user = db_session.query(Personnel).filter(Personnel.id == userid).first()

        # 检查车辆是否存在
        vehicle = (
            db_session.query(Vehicle, PersonnelParkingRelation)
            .join(PersonnelParkingRelation, Vehicle.plate == PersonnelParkingRelation.plate)
            .filter(PersonnelParkingRelation.personnel_id == user.id)
            .filter(Vehicle.plate == plate)
            .first()
        )
        if not vehicle:
            return json({"message": "Vehicle not found"}, status=404)

        # 更新车辆信息
        vehicle.permissions = new_permissions
        db_session.commit()

        return json({"message": "Vehicle updated successfully"})


@app.route("/vehicle/delete", methods=["POST"])
@requires_auth()
async def vehicle_delete(request):
    data = request.json
    plate = data.get("plate")

    userid = request.ctx.session.get("userid")

    db_session = get_session()
    user = db_session.query(Personnel).filter(Personnel.id == userid).first()

    # 删除车辆及相关关系
    vehicle = (
        db_session.query(Vehicle)
        .join(PersonnelParkingRelation, Vehicle.plate == PersonnelParkingRelation.plate)
        .filter(PersonnelParkingRelation.personnel_id == user.id)
        .filter(Vehicle.plate == plate)
        .first()
    )
    if not vehicle:
        return json({"message": "Vehicle not found"}, status=404)

    db_session.query(PersonnelParkingRelation).filter(PersonnelParkingRelation.plate == plate).delete()
    db_session.commit()

    return json({"message": "Vehicle deleted successfully"})


@app.route("/vehicle/access", methods=["GET", "POST"])
async def vehicle_access(request):
    if request.method == "GET":
        with open("templates/vehicle_access.html", 'r', encoding='utf-8') as f:
            return html(f.read())
    elif request.method == "POST":
        data = request.json
        plate = data.get("plate")
        parking_id = data.get("parking_id")
        action = data.get("action")

        db_session = get_session()

        # 检查停车场是否存在
        parking_area = db_session.query(ParkingArea).filter(ParkingArea.id == parking_id).first()
        if not parking_area:
            return json({"message": "Parking area not found"}, status=404)

        # 检查车辆是否存在，不存在则新建
        vehicle = db_session.query(Vehicle).filter(Vehicle.plate == plate).first()
        if not vehicle:
            vehicle = Vehicle(plate=plate, permissions='0')
            db_session.add(vehicle)
            db_session.commit()

        # 检查权限
        if int(vehicle.permissions) < int(parking_area.permissions):
            action = 'DENIED'

        # 记录车辆出入记录
        new_access_record = VehicleAccessRecord(
            plate=plate,
            parking_id=parking_id,
            action=action
        )

        db_session.add(new_access_record)
        db_session.commit()

        # 更新支付状态
        if action == 'IN':
            vehicle.paid = False
            vehicle.last_in = new_access_record.id  # 更新 last_in
        elif action == 'OUT':
            vehicle.last_out = new_access_record.id  # 更新 last_out
        db_session.commit()

        return json({"message": f"Vehicle access recorded successfully, action: {action}"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
