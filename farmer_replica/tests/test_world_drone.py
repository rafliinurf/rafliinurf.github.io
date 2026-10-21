import pytest

from game.clock import Clock, load_costs
from game.drone import Drone
from game.entities import load_entities
from game.inventory import Inventory
from game.world import GRASSLAND, SOIL, World


@pytest.fixture
def setup():
    defs = load_entities()
    world = World(4, defs)
    clock = Clock()
    inv = Inventory()
    drone = Drone(world, clock, inv)
    return world, clock, inv, drone


# --- data ---
def test_json_dimuat():
    assert "carrot" in load_entities()
    assert load_costs()["actions"]["move"] == {"success": 200, "fail": 1}


# --- wrap-around ---
def test_move_wrap_tepi(setup):
    world, clock, inv, drone = setup
    drone.perform("move", "west")
    assert (drone.x, drone.y) == (3, 0)
    drone.perform("move", "south")
    assert (drone.x, drone.y) == (3, 3)
    drone.perform("move", "east")
    drone.perform("move", "north")
    assert (drone.x, drone.y) == (0, 0)


def test_move_arah_salah_gagal_1_tick(setup):
    _, clock, _, drone = setup
    r = drone.perform("move", "atas")
    assert not r.success and r.cost == 1 and clock.tick_count == 1


# --- biaya tick ---
def test_biaya_move_berhasil_200(setup):
    _, clock, _, drone = setup
    r = drone.perform("move", "north")
    assert r.success and r.value is True and r.cost == 200 and clock.tick_count == 200


def test_biaya_sensor_1(setup):
    _, clock, _, drone = setup
    drone.perform("get_pos_x")
    drone.perform("get_pos_y")
    assert clock.tick_count == 2


def test_till_selalu_200(setup):
    _, clock, _, drone = setup
    drone.perform("till")
    drone.perform("till")
    assert clock.tick_count == 400


def test_aksi_gagal_1_tick(setup):
    _, clock, _, drone = setup
    r = drone.perform("plant", "carrot")  # tanah masih grassland
    assert not r.success and r.cost == 1


def test_biaya_tak_dikenal_error():
    with pytest.raises(KeyError):
        Clock().cost_of("terbang")


# --- pertumbuhan berbasis tick ---
def test_tumbuh_berdasarkan_tick_bukan_waktu_nyata(setup):
    world, _, _, drone = setup
    assert not drone.perform("can_harvest").value  # rumput baru, belum matang
    grow = world.defs["grass"].grow_ticks
    # 3 pasang gerak = 1200 tick; petak (0,0) dilewati dan umurnya terus naik
    for _ in range(3):
        drone.perform("move", "north")
        drone.perform("move", "south")
    assert world.tile(0, 0).age >= grow
    assert drone.perform("can_harvest").value


# --- harvest ---
def test_harvest_matang_beri_hasil_dan_rumput_tumbuh_lagi(setup):
    world, _, inv, drone = setup
    world.advance(world.defs["grass"].grow_ticks)
    r = drone.perform("harvest")
    assert r.success and r.value is True and inv.count("hay") == 1
    assert drone.last_harvest_event == {
        "x": 0,
        "y": 0,
        "entity": "grass",
        "mature": True,
        "progress": 1.0,
        "yields": {"hay": 1},
    }
    assert world.tile(0, 0).entity == "grass"
    # efek aksi berlaku dulu, lalu waktu berjalan: rumput baru ikut umur 200 tick
    assert world.tile(0, 0).age == 200


def test_upgrade_grass_menggandakan_hay_dan_tidak_menggandakan_wood(setup):
    world, _, inventory, drone = setup
    drone.grass_yield_multiplier = 4
    world.advance(world.defs["grass"].grow_ticks)

    drone.perform("harvest")

    assert inventory.count("hay") == 4
    assert world.tile(0, 0).age == 200

    inventory.add("wood", 5)
    drone.perform("plant", "bush")
    world.advance(world.defs["bush"].grow_ticks)
    drone.perform("harvest")

    assert inventory.count("wood") == 6


def test_clear_mereset_ladang_dan_posisi_tanpa_menghapus_inventory(setup):
    world, clock, inventory, drone = setup
    world.resize(3, 2)
    world.tile(0, 0).water = 0.75
    world.tile(1, 0).ground = SOIL
    world.tile(1, 0).entity = "carrot"
    world.tile(1, 0).age = 50
    inventory.add("hay", 12)
    drone.x, drone.y = 2, 1
    drone.last_dir = "west"

    result = drone.perform("clear")

    assert result.success and result.value is None and result.cost == 200
    assert clock.tick_count == 200
    assert (drone.x, drone.y, drone.last_dir) == (0, 0, None)
    assert inventory.count("hay") == 12
    assert all(
        tile.ground == GRASSLAND
        and tile.entity == "grass"
        and tile.water == 0
        and tile.age == 200
        for column in world.tiles
        for tile in column
    )


def test_harvest_belum_matang_hancur_tanpa_hasil(setup):
    world, _, inv, drone = setup
    r = drone.perform("harvest")
    assert r.success and r.value is True and inv.count("hay") == 0
    assert drone.last_harvest_event["mature"] is False
    assert drone.last_harvest_event["yields"] == {}


def test_harvest_petak_kosong_gagal(setup):
    world, clock, _, drone = setup
    world.tile(0, 0).entity = None
    r = drone.perform("harvest")
    assert not r.success and r.cost == 1


# --- plant & till ---
def test_till_mengubah_tanah_dan_menghapus_entitas(setup):
    world, _, _, drone = setup
    drone.perform("till")
    t = world.tile(0, 0)
    assert t.ground == SOIL and t.entity is None
    drone.perform("till")
    assert t.ground == GRASSLAND and t.entity == "grass"


def test_plant_wortel_butuh_soil_dan_biaya(setup):
    world, _, inv, drone = setup
    drone.perform("till")
    assert not drone.perform("plant", "carrot").success  # item kurang
    inv.add("hay", 512)
    inv.add("wood", 512)
    r = drone.perform("plant", "carrot")
    assert r.success and r.value is True and world.tile(0, 0).entity == "carrot"
    assert inv.count("hay") == 0 and inv.count("wood") == 0


def test_grass_dapat_ditanam_di_soil_dengan_biaya_kosong(setup):
    world, _, _, drone = setup
    drone.perform("till")

    result = drone.perform("plant", "grass")

    assert result.success and result.value is True
    assert world.tile(0, 0).entity == "grass"


def test_bush_dapat_menggantikan_rumput_yang_tumbuh_otomatis(setup):
    world, _, inv, drone = setup
    inv.add("wood", 5)
    result = drone.perform("plant", "bush")

    assert result.success
    assert world.tile(0, 0).entity == "bush"


def test_plant_tidak_menggantikan_tanaman_non_otomatis(setup):
    world, _, inv, drone = setup
    inv.add("wood", 5)
    assert drone.perform("plant", "bush").success

    result = drone.perform("plant", "bush")

    assert not result.success
    assert world.tile(0, 0).entity == "bush"


def test_resize_ke_lahan_1x3_mempertahankan_petakan_dan_wrap_per_sumbu(setup):
    world, _, _, drone = setup
    original = world.tile(0, 0)
    original.entity = "bush"
    original.age = 17

    world.resize(3, 1)

    assert (world.width, world.height, world.size) == (3, 1, 3)
    assert world.tile(0, 0) is original
    assert (world.tile(0, 0).entity, world.tile(0, 0).age) == ("bush", 17)
    assert world.tile(1, 0).entity == "grass"
    assert world.wrap(3, 0) == (0, 0)
    assert world.wrap(-1, 0) == (2, 0)
    assert world.wrap(1, 5) == (1, 0)
    assert drone.perform("get_world_size").value == 3


def test_upgrade_expand_membersihkan_lahan_dan_menumbuhkan_rumput_baru(setup):
    world, _, _, _ = setup
    world.tile(0, 0).ground = SOIL
    world.tile(0, 0).entity = "bush"
    world.tile(0, 0).age = 120

    world.expand_and_clear(3, 3)

    assert (world.width, world.height) == (3, 3)
    assert all(
        tile.ground == GRASSLAND
        and tile.entity == "grass"
        and tile.age == 0
        for column in world.tiles
        for tile in column
    )


def test_siklus_wortel_penuh(setup):
    world, _, inv, drone = setup
    inv.add("hay", 512)
    inv.add("wood", 512)
    drone.perform("till")
    drone.perform("plant", "carrot")
    world.advance(world.defs["carrot"].grow_ticks)
    assert drone.perform("can_harvest").value
    drone.perform("harvest")
    assert inv.count("carrot") == 1


def test_water_meningkatkan_pertumbuhan_dari_1x_sampai_5x():
    defs = load_entities()
    dry_world = World(1, defs)
    wet_world = World(1, defs)
    wet_world.tile(0, 0).water = 1.0

    dry_world.advance(400)
    wet_world.advance(400)

    assert dry_world.tile(0, 0).age == 400
    assert wet_world.tile(0, 0).age == pytest.approx(1992.0066)


def test_air_mengering_rata_rata_satu_persen_per_detik():
    world = World(1, load_entities())
    world.tile(0, 0).water = 1.0

    world.advance(400)

    assert world.tile(0, 0).water == pytest.approx(0.99)


def test_use_item_menggunakan_tank_maksimal_satu_air_dan_biaya_wiki(setup):
    world, clock, inventory, drone = setup
    inventory.add("water", 6)
    world.tile(0, 0).water = 0.5

    result = drone.perform("use_item", "water", 4)

    assert result.success and result.cost == 200
    assert inventory.count("water") == 4
    assert world.tile(0, 0).water == pytest.approx(0.99 ** 0.5)
    assert clock.tick_count == 200


def test_use_item_gagal_tanpa_air_dan_menolak_jumlah_invalid(setup):
    _, clock, _, drone = setup

    result = drone.perform("use_item", "water")

    assert not result.success and result.cost == 1
    assert clock.tick_count == 1
    for invalid_count in (0, -1, 1.5, True):
        assert not drone.perform("use_item", "water", invalid_count).success


def test_water_supply_otomatis_setiap_sepulu_detik_dan_dikalikan_tier(setup):
    _, _, inventory, drone = setup
    drone.speed_multiplier = 2
    drone.watering_tanks_per_10_seconds = 2
    drone._advance_world(7999)
    assert inventory.count("water") == 0

    drone._advance_world(1)

    assert inventory.count("water") == 2
    assert drone.water_time_seconds == pytest.approx(0)


def test_water_supply_tidak_terlambat_karena_rounding_per_tick(setup):
    _, _, inventory, drone = setup
    drone.watering_tanks_per_10_seconds = 1

    for _ in range(4000):
        drone._advance_world(1)

    assert inventory.count("water") == 1
    assert drone.water_time_seconds == pytest.approx(0)


# --- log aksi terpusat ---
def test_log_mencatat_semua_lewat_perform(setup):
    _, _, _, drone = setup
    drone.perform("move", "north")
    drone.perform("get_pos_y")
    assert [e[1] for e in drone.log] == ["move", "get_pos_y"]
    assert drone.log[1][0] == 200  # tick sebelum aksi kedua
