from flask_bcrypt import Bcrypt
from flask_jwt_extended import get_jwt_identity
from app.persistence.repository import InMemoryRepository
from app.models.user import User
from app.models.review import Review
from app.models.amenity import Amenity
from app.models.place import Place
from app.models import storage
from app.persistence.repository import SQLAlchemyRepository
from app.persistence.user_repository import UserRepository
from app import db
from app.persistence.place_repository import PlaceRepository
from app.persistence.review_repository import ReviewRepository
from app.persistence.amenity_repository import AmenityRepository


bcrypt = Bcrypt()


# Exception handler for validation errors
class ValidationError(Exception):
    pass


class HBnBFacade:
    """
    The HBnB facade enables interaction with object repositories
    (users, places, reviews, amenities).
    This class abstracts CRUD operations for multiple entities.
    """

    def __init__(self):
        self.user_repo = InMemoryRepository()
        self.place_repo = InMemoryRepository()
        self.review_repo = InMemoryRepository()
        self.amenity_repo = InMemoryRepository()
        self.user_repo = SQLAlchemyRepository(User)
        self.user_repo = UserRepository()
        self.place_repo = PlaceRepository()
        self.review_repo = ReviewRepository()
        self.amenity_repo = AmenityRepository()

    def admin_update_user(self, user_id, user_data):
        """
        Admin-only method to update any user's details including email and
        password

        Args:
            user_id (str): The ID of the user to update
            user_data (dict): Dictionary containing the user data to update

        Returns:
            User: The updated user object

        Raises:
            ValueError: If user not found or email already exists
        """
        user = self.get_user(user_id)
        if not user:
            raise ValueError("User not found")

        # Handle email update
        if 'email' in user_data:
            existing_user = self.get_user_by_email(user_data['email'])
            if existing_user and existing_user.id != user_id:
                raise ValueError("Email already in use")
            user.email = user_data['email']

        # Handle password update
        if 'password' in user_data:
            hashed_password = bcrypt.generate_password_hash(
                user_data['password']).decode('utf-8')
            user.password = hashed_password

        # Update other fields
        if 'first_name' in user_data:
            user.first_name = user_data['first_name']
        if 'last_name' in user_data:
            user.last_name = user_data['last_name']
        if 'is_admin' in user_data:
            user.is_admin = user_data['is_admin']

        storage.save()
        return user

    def admin_delete_place(self, place_id):
        """
        Admin-only method to delete any place without ownership check

        Args:
            place_id (str): The ID of the place to delete

        Returns:
            bool: True if deletion was successful

        Raises:
            ValueError: If place not found
        """
        place = self.get_place(place_id)
        if not place:
            raise ValueError("Place not found")

        storage.delete(place)
        storage.save()
        return True

    def admin_update_review(self, review_id, review_data):
        """
        Admin-only method to update any review without ownership check

        Args:
            review_id (str): The ID of the review to update
            review_data (dict): Dictionary containing the review data to update

        Returns:
            Review: The updated review object

        Raises:
            ValueError: If review not found or invalid rating
        """
        review = self.get_review(review_id)
        if not review:
            raise ValueError("Review not found")

        if 'text' in review_data:
            review.text = review_data['text']
        if 'rating' in review_data:
            review.rating = self.validate_rating(review_data['rating'])

        storage.save()
        return review

    # Helper method for validating ratings
    def validate_rating(self, rating):
        """Validate that a rating is between 1 and 5"""
        try:
            rating = int(rating)
            if not 1 <= rating <= 5:
                raise ValueError
            return rating
        except (TypeError, ValueError):
            raise ValueError("Rating must be an integer between 1 and 5")

    # ---------------------------- User Management ----------------------------

    def create_user(self, user_data: dict) -> User:
        """Create a new user."""
        print("\n=== Creating User in Facade ===")
        try:
            # VCheck if the email already exists
            existing_user = self.get_user_by_email(user_data.get('email'))
            if existing_user:
                raise ValueError("Email already in use")

            # Obtain password and other user data
            password = user_data.get('password')
            print("Received raw password in facade")

            user = User(
                first_name=user_data["first_name"],
                last_name=user_data["last_name"],
                email=user_data["email"],
                password=password,  # Pass raw password to User class
                is_admin=user_data.get("is_admin", False)
            )

            print(f"User created in facade. Final password hash: {
                user.password[:20]}...")

            # Ajouter l'utilisateur via le SQLAlchemyRepository
            self.user_repo.add(user)
            return user

        except Exception as e:
            print(f"Error in create_user: {str(e)}")
            raise ValueError(str(e))

    def update_user(self, user_id, user_data):
        current_user_id = get_jwt_identity()

        if user_id != current_user_id:
            raise ValidationError("Unauthorized access")

        user = self.user_repo.get(user_id)
        if not user:
            raise ValidationError("User not found")

        # Mise à jour des champs utilisateur autorisés
        if 'first_name' in user_data:
            user.first_name = user_data['first_name']
        if 'last_name' in user_data:
            user.last_name = user_data['last_name']
        if 'email' in user_data or 'password' in user_data:
            print("Modification de l'email ou du mot de passe interdite.")

        db.session.commit()  # Sauvegarder les changements
        return user

    def delete_user(self, user_id):
        user = self.user_repo.get(user_id)
        if not user:
            raise ValidationError("User not found")

        # Suppression via SQLAlchemyRepository
        self.user_repo.delete(user_id)

    def get_user(self, user_id):
        return self.user_repo.get(user_id)

    def get_user_by_email(self, email):
        # Rechercher l'utilisateur par email en utilisant SQLAlchemy
        return self.user_repo.get_by_attribute("email", email)

    def get_all_users(self):
        return self.user_repo.get_all()

    # ---------------------------- Review Management --------------------------

    def create_review(self, review_data):
        user_id = review_data.get('user_id')
        place_id = review_data.get('place_id')
        print(f"Debug: User ID = {user_id}, Place ID = {place_id}")

        user = storage.get(user_id)
        if not user:
            print(f"Error: User {user_id} not found.")
            raise ValidationError(f"User with ID {user_id} not found")

        place = storage.get(place_id)
        if not place:
            print(f"Error: Place {place_id} not found.")
            raise ValidationError(f"Place with ID {place_id} not found")

        if place.owner_id == user_id:
            raise ValidationError("Owners cannot review their own place")

        existing_review = self.get_user_review_for_place(user_id, place_id)
        if existing_review:
            raise ValidationError("User has already reviewed this place")

        review = Review(
            text=review_data['text'],
            rating=review_data['rating'],
            user_id=user_id,
            place_id=place_id
        )
        storage.add(review)
        storage.save()
        print(f"Review created with ID: {review.id}")
        return review

    def get_user_review_for_place(self, user_id, place_id):
        """
        Checks whether a user has already left a review for a specific
        location.

        Args:
        user_id (str): The user's identifier.
        place_id (str): The place identifier.

        Returns:
            Review or None: The review if found, otherwise None.
        """
        reviews = storage.get_all(Review)
        for review in reviews:
            if review.user_id == user_id and review.place_id == place_id:
                return review
        return None

    def get_review(self, review_id):
        return storage.get(review_id)

    def get_all_reviews(self):
        return storage.get_all(Review)

    def update_review(self, review_id, review_data):
        review = storage.get(review_id)
        if not review:
            raise ValidationError("Review not found")

        current_user_id = get_jwt_identity()
        if review.user_id != current_user_id:
            return {"error": "Unauthorized access"}, 403

        if 'text' in review_data:
            review.text = review_data['text']
        if 'rating' in review_data:
            review.rating = review_data['rating']

        storage.save()
        return review

    def delete_review(self, review_id):
        print(f"Attempting to delete review with ID: {review_id}")
        review = storage.get(review_id)
        if not review:
            print(f"Error: Review with ID {review_id} not found.")
            return {
                "message": (
                    "Review not found. It might have already been deleted."
                )
            }, 200

        current_user_id = get_jwt_identity()
        if review.user_id != current_user_id:
            return {"error": "Unauthorized access"}, 403

        storage.delete(review)
        storage.save()
        print(f"Review with ID {review_id} successfully deleted.")
        return {"message": "Review deleted successfully"}, 200

    # ---------------------------- Amenity Management -------------------------

    def create_amenity(self, amenity_data):
        name = amenity_data.get('name')
        if not name:
            return ValidationError, "Name is required"

        # Create a new Amenity object and save it to storage
        new_amenity = Amenity(name=name)
        storage.add(new_amenity)
        storage.save()
        return new_amenity

    def get_amenity(self, amenity_id):
        """
        Retrieves an amenity by ID from the repository.
        """
        amenity = self.amenity_repo.get(amenity_id)
        if not amenity:
            return None, "Amenity not found"
        return amenity

    def get_all_amenities(self):
        return self.amenity_repo.get_all()

    def update_amenity(self, amenity_id, amenity_data):
        amenity = self.amenity_repo.get(amenity_id)
        if not amenity:
            return None, "Amenity not found"

        # Update the name if provided
        amenity.name = amenity_data.get('name', amenity.name)
        # Update the amenity data
        self.amenity_repo.update(amenity_id, amenity.__dict__)
        return amenity, None

    def delete_amenity(self, amenity_id):
        amenity = self.amenity_repo.get(amenity_id)
        if not amenity:
            return False, "Amenity not found"
        self.amenity_repo.delete(amenity_id)
        return True

    # ---------------------------- Place Management ---------------------------

    def create_place(self, place_data):
        """Create a new place."""
        print("\n=== Creating Place ===")
        print(f"Place data: {place_data}")

        self.validate_place_data(place_data)

        new_place = Place(
            title=place_data['title'],
            description=place_data.get('description', ''),
            price=place_data['price'],
            latitude=place_data['latitude'],
            longitude=place_data['longitude'],
            owner_id=place_data['owner_id']
        )

        # Add the place to storage
        storage.add(new_place)
        storage.save()
        print(f"Place created with ID: {new_place.id}")
        return new_place

    def validate_place_data(self, place_data):
        """
        Internal function to validate place data.
        """
        if not isinstance(place_data.get('price'), (int, float)) or not (
             1 <= place_data.get("price") <= 1000000):
            raise ValidationError(
                'Price must be a number between 1 and 1000000')
        if not isinstance(place_data.get('latitude'), (int, float)) or not (
             -90 <= place_data.get("latitude") <= 90):
            raise ValidationError(
                'Latitude must be a number between -90 and 90')
        if not isinstance(place_data.get('longitude'), (int, float)) or not (
             -180 <= place_data.get("longitude") <= 180):
            raise ValidationError(
                'Longitude must be a number between -180 and 180')
        if not isinstance(place_data.get('title'), str) or not (
             1 <= len(place_data.get("title", "")) <= 50):
            raise ValidationError('Title must be between 1 and 50 characters')
        if 'description' in place_data and not (
             1 <= len(place_data['description']) <= 500):
            raise ValidationError(
                'Description must be between 1 and 500 characters')

    def get_place(self, place_id):
        """Get a place by ID."""
        print(f"\n=== Getting Place {place_id} ===")
        # Use storage instead of place_repo
        place = storage.get(place_id)
        print(f"Place found: {place is not None}")
        if place:
            print(f"Place details: {place.to_dict()}")
        return place

    def get_all_places(self):
        return self.place_repo.get_all()

    def update_place(self, place_id, place_data):
        place = self.place_repo.get(place_id)
        if not place:
            return {"error": "Place not found"}, 404

        current_user_id = get_jwt_identity()
        if place.owner_id != current_user_id:
            return {"error": "Unauthorized access"}, 403

        for key, value in place_data.items():
            setattr(place, key, value)

        storage.save()
        return place

    def delete_place(self, place_id):
        place = storage.get(place_id)
        if not place:
            return {"error": "Place not found"}, 404

        current_user_id = get_jwt_identity()
        if place.owner_id != current_user_id:
            return {"error": "Unauthorized access"}, 403

        storage.delete(place)
        storage.save()
        return {"message": "Place deleted successfully"}, 200
