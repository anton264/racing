import csv
import os
import statistics
from django.core.management.base import BaseCommand
from telemetry.models import Game, Car, Track, Lap, FastLap
from telemetry.influx import Influx
from telemetry.fast_lap_analyzer import FastLapAnalyzer
import logging
from django.db import connection


class Command(BaseCommand):
    help = "Closes the specified poll for voting"

    def add_arguments(self, parser):
        # add argument for list of lap ids as integers separated by commas
        parser.add_argument(
            "-l",
            "--lap-ids",
            nargs="+",
            type=int,
            default=None,
            help="list of lap ids to analyze",
        )

        # add optional argument for game, track and car
        parser.add_argument(
            "-g",
            "--game",
            nargs="?",
            type=str,
            default=None,
            help="game name to analyze",
        )
        parser.add_argument(
            "-t",
            "--track",
            nargs="?",
            type=str,
            default=None,
            help="track name to analyze",
        )
        parser.add_argument(
            "-c",
            "--car",
            nargs="?",
            type=str,
            default=None,
            help="car name to analyze",
        )
        parser.add_argument("-i", "--import-csv", nargs="*", type=str, default=None)
        parser.add_argument("--from-bucket", nargs="?", type=str, default="racing")
        parser.add_argument("-n", "--new", action="store_true", help="only analyze new coaches")
        parser.add_argument(
            "-s",
            "--save-csv",
            nargs="?",
            type=str,
            default=None,
            help="save to csv",
        )
        parser.add_argument("--create-empty", action="store_true")
        parser.add_argument("--copy-influx", action="store_true")

    def import_csv(self, options):
        for csv_file in options["import_csv"]:
            basename = os.path.basename(csv_file).split(".")[0]
            car, track = basename.split("-")
            game, created = Game.objects.get_or_create(name="iRacing")
            rcar, created = Car.objects.get_or_create(name=car, game=game)
            rtrack, created = Track.objects.get_or_create(name=track, game=game)
            fast_lap, created = FastLap.objects.get_or_create(car=rcar, track=rtrack, game=game)

            with open(csv_file, mode="r") as infile:
                reader = csv.DictReader(infile)
                for row in reader:
                    brakepoint = {
                        "start": 0,
                        "end": 0,
                        "mark": "",
                        "turn_in": 0,
                        "force": 0,
                        "gear": 0,
                        "speed": 0,
                        "stop": 0,
                        "accelerate": 0,
                    }
                    for key in row:
                        if row[key]:
                            if key == "mark" or key == "turn":
                                brakepoint[key] = row[key]
                            else:
                                brakepoint[key] = int(row[key])
                        else:
                            brakepoint[key] = 0
                    print(brakepoint)
                    segment, created = fast_lap.fast_lap_segments.get_or_create(
                        start=brakepoint["start"],
                        end=brakepoint["end"],
                        mark=brakepoint["mark"],
                        gear=brakepoint["gear"],
                        force=brakepoint["force"],
                        speed=brakepoint["speed"],
                        stop=brakepoint["stop"],
                        accelerate=brakepoint["accelerate"],
                        brake=brakepoint["brake"],
                    )
                    print(segment)
                    print(created)

            self.stdout.write(self.style.SUCCESS('Successfully imported "%s"' % csv_file))

    def handle(self, *args, **options):
        influx = Influx()
        influx_fast_sessions = set()
        from_bucket = options["from_bucket"]
        if options["copy_influx"]:
            influx_fast_sessions = influx.session_ids(bucket="fast_laps")

        if options["save_csv"]:
            csv_file = open(options["save_csv"], "w")
            # open a file for appending
            csv_writer = csv.DictWriter(
                csv_file,
                fieldnames=[
                    "game",
                    "session",
                    "track",
                    "car",
                    "lap",
                    "start",
                    "end",
                    "time",
                    "length",
                    "valid",
                ],
            )
            csv_writer.writeheader()

        if options["import_csv"]:
            self.import_csv(options["import_csv"])

        if options["lap_ids"]:
            laps = Lap.objects.filter(pk__in=options["lap_ids"])
            self.analyze_fast_laps(laps)
            return

        where = []
        filter_game = None
        if options["game"]:
            filter_game = Game.objects.get(name=options["game"])
        if options["track"]:
            track = Track.objects.get(name=options["track"])
            where.append(f" track_id={track.pk}")
        if options["car"]:
            # get the first car with this name
            car = filter_game.cars.filter(name=options["car"]).first()
            where.append(f"car_id={car.pk}")

        where_clause = ""
        if where:
            where_clause = "where " + " and ".join(where)

        sql = f"select count(id) as c, track_id, car_id from telemetry_lap {where_clause} group by track_id, car_id"

        if options["create_empty"]:
            self.create_empty(car=car, track=track, game=filter_game)
            return

        with connection.cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()

        for count, track_id, car_id in rows:
            car = Car.objects.get(id=car_id)
            track = Track.objects.get(id=track_id)
            game = car.game
            if filter_game and filter_game != car.game:
                continue

            if options["new"]:
                if FastLap.objects.filter(car=car, track=track, game=game, driver=None).exists():
                    logging.info(f"Fastlap already exists for {game.name} / {track.name} / {car.name}")
                    continue

            logging.info(f"{count} laps for {game.name} / {track.name} / {car.name}")

            # get all lap time and length for this car and track
            sql = f"select time, length from telemetry_lap where track_id={track.pk} and car_id={car.pk}"
            with connection.cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchall()

            times = [row[0] for row in rows]
            lengths = [row[1] for row in rows]
            median_time = statistics.median(times)
            median_length = statistics.median(lengths)
            logging.debug(f"median time: {median_time}, median length: {median_length}")

            laps = Lap.objects.filter(
                track=track,
                car=car,
                length__gt=median_length * 0.95,
                length__lt=median_length * 1.05,
                time__gt=median_time * 0.95,
                time__lt=median_time * 1.05,
            ).order_by("-valid", "time")[:10]

            if laps.count() == 0:
                logging.info("No laps found for threshold")
                continue

            lap = laps[0]
            fast_time = lap.time
            fast_laps = [lap]
            # threshold is 120% of the fastest lap
            threshold = fast_time * 1.2

            for lap in laps[1:]:
                if lap.time <= threshold:
                    # print(f"{lap.time} is <= {threshold}")
                    fast_laps.append(lap)
                    logging.debug(lap)

            if options["copy_influx"]:
                sessions = set()
                for lap in fast_laps:
                    sessions.add(lap.session)

                for session in sessions:
                    if session.session_id in influx_fast_sessions:
                        influx_fast_sessions.remove(session.session_id)
                        continue
                    influx.copy_session(
                        session.session_id, start=session.start, end=session.end, from_bucket=from_bucket
                    )

            if options["save_csv"]:
                for lap in fast_laps:
                    row = {
                        "game": game.name,
                        "session": lap.session.session_id,
                        "track": track.name,
                        "car": lap.car.name,
                        "lap": lap.number,
                        "start": lap.start,
                        "end": lap.end,
                        "time": lap.time,
                        "length": lap.length,
                        "valid": lap.valid,
                    }
                    csv_writer.writerow(row)
            else:
                self.analyze_fast_laps(fast_laps)

        if options["save_csv"]:
            csv_file.close()

        if options["copy_influx"]:
            logging.debug(f"fast sessions to be deleted: {influx_fast_sessions}")

    def analyze_fast_laps(self, fast_laps):
        fl = FastLapAnalyzer(fast_laps)
        result = fl.analyze()
        if result:
            track_info = result[0]
            data = result[1]
            used_laps = result[2]
            self.save_fastlap(track_info, data, laps=used_laps)

    def create_empty(self, car=None, track=None, game=None):
        fast_lap, created = FastLap.objects.get_or_create(car=car, track=track, game=game, driver=None)
        logging.debug(f"created: {created}, fast_lap: {fast_lap}")

    def save_fastlap(self, track_info, data, laps=[]):
        if not laps:
            logging.error("no laps")
            return
        lap = laps[0]
        car = lap.car
        track = lap.track
        game = lap.session.game
        fast_lap, created = FastLap.objects.get_or_create(car=car, track=track, game=game, driver=None)
        fast_lap.data = data
        fast_lap.laps.set(laps)
        fast_lap.save()
        fast_lap.fast_lap_segments.all().delete()
        i = 1
        for s in track_info:
            s["turn"] = i
            fast_lap.fast_lap_segments.create(
                turn=i,
                mark=s["mark"],
                start=s["start"],
                end=s["end"],
                force=s["force"],
                gear=s["gear"],
                speed=s["speed"],
            )
            i += 1
        # also delete user segments
        # FIXME only delete user segements if they changed?
        r = FastLap.objects.filter(car=car, track=track, game=game).exclude(driver=None).delete()
        logging.debug(f"deleted {r} user segments")
