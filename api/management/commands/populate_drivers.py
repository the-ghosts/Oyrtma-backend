"""
Django management command to populate DriverInformation with realistic sample data.
Generates 500+ drivers with 1-4 vehicles each, distributed across Nigerian states.
"""

import random
from django.core.management.base import BaseCommand
from django.db import transaction, models
from api.models import DriverInformation

# Nigerian States
NIGERIAN_STATES = [
    'Lagos', 'Oyo', 'Abuja (FCT)', 'Kano', 'Katsina', 'Kaduna', 'Sokoto', 'Kebbi',
    'Zamfara', 'Plateau', 'Nasarawa', 'Taraba', 'Adamawa', 'Borno', 'Yobe',
    'Bauchi', 'Gombe', 'Enugu', 'Ebonyi', 'Edo', 'Delta', 'Bayelsa', 'Rivers',
    'Akwa Ibom', 'Cross River', 'Imo', 'Abia', 'Anambra', 'Osun', 'Ondo', 'Ekiti',
]

# Common Nigerian first names
FIRST_NAMES = [
    'Chidi', 'Ngozi', 'Tunde', 'Funke', 'Ahmed', 'Aisha', 'Emeka', 'Zainab',
    'Kofi', 'Amara', 'Ibrahim', 'Fatima', 'Seun', 'Chioma', 'Adebayo', 'Hauwa',
    'Bola', 'Nkechi', 'Musa', 'Jumoke', 'Yusuf', 'Zara', 'Adekunle', 'Blessing',
    'Karim', 'Ifeanyi', 'Hassan', 'Uchenna', 'Rashid', 'Khadija', 'Deji', 'Toyin',
    'Malik', 'Adanna', 'Samson', 'Patience', 'Taiwo', 'Uche', 'Aliyu', 'Monica',
    'Rasheed', 'Okafor', 'Abdullahi', 'Efe', 'Jide', 'Amina', 'Kabir', 'Ifeoma',
    'Ismail', 'Isioma', 'Tijani', 'Nneka', 'Landry', 'Glory', 'Akeem', 'Stella',
]

# Common Nigerian last names
LAST_NAMES = [
    'Okonkwo', 'Adeyemi', 'Ibrahim', 'Okafor', 'Hassan', 'Smith', 'Johnson', 'Williams',
    'Brown', 'Jones', 'Miller', 'Davis', 'Wilson', 'Moore', 'Taylor', 'Anderson',
    'Abiola', 'Oluwaseun', 'Bello', 'Afolayan', 'Nwosu', 'Ezeoke', 'Usman', 'Chukwu',
    'Adebisi', 'Ade-ojo', 'Adeleke', 'Adesokan', 'Akande', 'Akinsanya', 'Adeyokunnu',
    'Adegunna', 'Adenowo', 'Ajala', 'Ajayi', 'Akinkugbe', 'Alamide', 'Alabi', 'Alade',
    'Alaka', 'Alaku', 'Alao', 'Alatise', 'Alawode', 'Alayande', 'Alayande', 'Alcantara',
    'Aldred', 'Alegbeleye', 'Alegbile', 'Alemika', 'Aleru', 'Ales', 'Aleshinloye',
]

# Vehicle types and models
VEHICLE_TYPES = [
    'Toyota Camry', 'Toyota Corolla', 'Toyota Hilux', 'Honda Civic', 'Honda Accord',
    'Nissan Altima', 'Nissan Datsun', 'Hyundai Elantra', 'Hyundai Accent',
    'Kia Rio', 'Kia Optima', 'Mercedes C-Class', 'BMW 3 Series', 'Audi A4',
    'Volkswagen Golf', 'Ford Focus', 'Mazda 3', 'Chevrolet Cruze', 'Peugeot 504',
    'Renault Clio', 'Maruti Swift', 'Daihatsu Charade', 'Opel Astra', 'Volvo XC60',
    'Lexus RX', 'Range Rover', 'Jeep Wrangler', 'Isuzu Pickup', 'DAF Truck',
    'Volvo Truck', 'Howo Truck', 'Mitsubishi Lancer', 'Subaru Outback', 'Porsche 911',
]

# Plate number prefixes by state (realistic Nigerian plate format)
PLATE_PREFIXES = {
    'Lagos': 'LG',
    'Oyo': 'OY',
    'Abuja (FCT)': 'AB',
    'Kano': 'KN',
    'Katsina': 'KT',
    'Kaduna': 'KD',
    'Sokoto': 'SK',
    'Kebbi': 'KB',
    'Zamfara': 'ZM',
    'Plateau': 'PL',
    'Nasarawa': 'NS',
    'Taraba': 'TR',
    'Adamawa': 'AD',
    'Borno': 'BO',
    'Yobe': 'YB',
    'Bauchi': 'BC',
    'Gombe': 'GM',
    'Enugu': 'EN',
    'Ebonyi': 'EB',
    'Edo': 'ED',
    'Delta': 'DT',
    'Bayelsa': 'BY',
    'Rivers': 'RV',
    'Akwa Ibom': 'AK',
    'Cross River': 'CR',
    'Imo': 'IM',
    'Abia': 'AB',
    'Anambra': 'AN',
    'Osun': 'OS',
    'Ondo': 'OD',
    'Ekiti': 'EK',
}


class Command(BaseCommand):
    help = 'Populate DriverInformation with 500+ realistic sample drivers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=500,
            help='Number of drivers to create (default: 500)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear all existing driver data before populating'
        )

    @transaction.atomic
    def handle(self, *args, **options):
        count = options['count']
        clear = options['clear']

        if clear:
            self.stdout.write(self.style.WARNING('Clearing existing driver data...'))
            DriverInformation.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('✓ Cleared existing data'))

        self.stdout.write(self.style.SUCCESS(f'🚗 Starting to populate {count} drivers...'))

        drivers_data = self._generate_driver_data(count)
        
        # Bulk create for efficiency
        drivers = [DriverInformation(**data) for data in drivers_data]
        
        created = DriverInformation.objects.bulk_create(drivers, batch_size=100)
        
        self.stdout.write(self.style.SUCCESS(f'✓ Successfully created {len(created)} driver records'))
        
        # Print statistics
        self._print_statistics()

    def _generate_driver_data(self, count):
        """Generate realistic driver data with multiple vehicles per driver"""
        # Test phone numbers (from user) - formatted with +234 prefix
        test_phone_numbers = [
            '+2349157405905', '+2348159551887', '+2348102443683',
            '+2349151404253', '+2349045816857', '+2348163540006'
        ]
        
        drivers_data = []
        created_plates = set()
        
        # Calculate how many drivers to create (some will have multiple vehicles)
        base_drivers = count // 2  # Half will have 1-2 vehicles, half will have 1-4
        
        driver_id = 1
        for i in range(base_drivers):
            first_name = random.choice(FIRST_NAMES)
            last_name = random.choice(LAST_NAMES)
            driver_name = f"{first_name} {last_name}"
            
            state = random.choice(NIGERIAN_STATES)
            prefix = PLATE_PREFIXES.get(state, 'XX')
            
            # Generate license number
            license_number = f"DL/{state[:2].upper()}/{random.randint(100000, 999999)}/2024"
            
            # Distribute test phone numbers evenly across all drivers
            phone = test_phone_numbers[i % len(test_phone_numbers)]
            
            # Generate email
            email = f"{first_name.lower()}.{last_name.lower()}{random.randint(1, 999)}@email.com"
            
            # Decide how many vehicles this driver has (weighted distribution)
            num_vehicles = random.choices([1, 2, 3, 4], weights=[50, 35, 10, 5])[0]
            
            # Create plate numbers for this driver
            for vehicle_idx in range(num_vehicles):
                # Generate unique plate number
                while True:
                    plate_number = f"{prefix}-{random.randint(100, 999)}-{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}"
                    if plate_number not in created_plates:
                        created_plates.add(plate_number)
                        break
                
                driver_data = {
                    'plate_number': plate_number,
                    'phone_number': phone,
                    'driver_name': driver_name,
                    'state': state,
                    'license_number': license_number,
                    'email': email,
                    'vehicle_type': random.choice(VEHICLE_TYPES),
                    'is_active': random.choices([True, False], weights=[95, 5])[0],
                }
                drivers_data.append(driver_data)
        
        return drivers_data

    def _print_statistics(self):
        """Print statistics about the populated data"""
        self.stdout.write(self.style.SUCCESS('\n📊 Driver Data Statistics:'))
        
        total = DriverInformation.objects.count()
        by_state = DriverInformation.objects.values('state').count()
        active = DriverInformation.objects.filter(is_active=True).count()
        inactive = DriverInformation.objects.filter(is_active=False).count()
        
        self.stdout.write(f'  Total drivers: {total}')
        self.stdout.write(f'  States covered: {by_state}')
        self.stdout.write(f'  Active: {active}')
        self.stdout.write(f'  Inactive: {inactive}')
        
        # Show top 5 states by driver count
        top_states = DriverInformation.objects.values('state').annotate(
            count=models.Count('id')
        ).order_by('-count')[:5]
        
        self.stdout.write('\n  Top 5 states:')
        for entry in top_states:
            self.stdout.write(f'    {entry["state"]}: {entry["count"]} drivers')
        
        # Show vehicle distribution
        vehicle_types = DriverInformation.objects.values('vehicle_type').annotate(
            count=models.Count('id')
        ).order_by('-count')[:5]
        
        self.stdout.write('\n  Top 5 vehicle types:')
        for entry in vehicle_types:
            self.stdout.write(f'    {entry["vehicle_type"]}: {entry["count"]} vehicles')
